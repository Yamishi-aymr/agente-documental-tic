
"""
Sincronización documental:
Google Drive -> OpenAI Vector Store.

Conserva los nombres originales y actualiza los
documentos nuevos, modificados o renombrados.
"""

import json
import os
import threading

from pathlib import Path
from openai import OpenAI

from app.core.config import settings
from app.services.drive_service import DriveService


MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "manifest.json"
)

_LOCK = threading.Lock()

SUPPORTED = {
    "application/pdf",
    "text/plain",
    "application/vnd.google-apps.document",
}


class SyncService:

    def __init__(self, client=None, drive=None):
        self.client = client or OpenAI(
            api_key=settings.openai_api_key
        )
        self.drive = drive or DriveService()

    @staticmethod
    def load_manifest() -> dict:
        if not MANIFEST.exists():
            return {
                "vector_store_id": "",
                "documents": {}
            }

        return json.loads(
            MANIFEST.read_text(encoding="utf-8")
        )

    @staticmethod
    def save_manifest(data: dict):
        MANIFEST.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        tmp = MANIFEST.with_suffix(".tmp")

        tmp.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        os.replace(tmp, MANIFEST)

    def get_store(self, manifest):
        vector_id = (
            settings.vector_store_id
            or manifest.get("vector_store_id")
        )

        if not vector_id:
            vector_id = self.client.vector_stores.create(
                name="Archivo TIC IA - Documentos"
            ).id

        manifest["vector_store_id"] = vector_id
        return vector_id

    def needs_update(self, item, previous):
        """
        Detecta modificaciones, cambios de nombre
        y archivos antiguos con nombres temporales.
        """

        if not previous:
            return True

        if (
            previous.get("modified_time")
            != item.get("modifiedTime")
        ):
            return True

        if previous.get("name") != item.get("name"):
            return True

        file_id = previous.get("openai_file_id")

        if not file_id:
            return True

        # Verificar el nombre almacenado en OpenAI.
        try:
            file_info = self.client.files.retrieve(file_id)

            expected_name = item["name"]

            if (
                item["mimeType"]
                == "application/vnd.google-apps.document"
            ):
                expected_name += ".txt"

            expected_name = expected_name.replace(
                "\\", "_"
            ).replace("/", "_")

            return file_info.filename != expected_name

        except Exception:
            # Si el archivo antiguo no puede consultarse,
            # volver a intentar indexarlo.
            return True

    def upload_document(self, item, store):
        """
        Descarga el documento de Drive y lo sube
        conservando un nombre reconocible.
        """

        raw, filename, _ = self.drive.get_bytes(item)

        if not raw:
            raise ValueError("El archivo está vacío")

        filename = filename.replace(
            "\\", "_"
        ).replace("/", "_")

        upload = (
            self.client.vector_stores.files.upload_and_poll(
                vector_store_id=store,
                file=(filename, raw)
            )
        )

        if upload.status != "completed":
            raise RuntimeError(
                "Indexación no completada: "
                + upload.status
            )

        return upload.id

    @staticmethod
    def document_url(item, drive_id):
        if item.get("webViewLink"):
            return item["webViewLink"]

        if (
            item["mimeType"]
            == "application/vnd.google-apps.document"
        ):
            return (
                "https://docs.google.com/document/d/"
                + drive_id
                + "/edit"
            )

        return (
            "https://drive.google.com/file/d/"
            + drive_id
            + "/view"
        )

    def sync(self):

        if not _LOCK.acquire(blocking=False):
            raise RuntimeError(
                "Ya existe una sincronización en curso"
            )

        try:
            manifest = self.load_manifest()

            docs = manifest.setdefault(
                "documents", {}
            )

            store = self.get_store(manifest)

            self.save_manifest(manifest)

            source = self.drive.list_files(
                settings.drive_folder_id
            )

            eligible = {
                item["id"]: item
                for item in source
                if item["mimeType"] in SUPPORTED
            }

            stats = {
                "added": 0,
                "updated": 0,
                "removed": 0,
                "unchanged": 0,
                "errors": []
            }

            # Procesar archivos actuales de Drive.
            for drive_id, item in eligible.items():

                previous = docs.get(drive_id)

                try:
                    if not self.needs_update(
                        item, previous
                    ):
                        stats["unchanged"] += 1
                        continue

                    # Subir y esperar la indexación.
                    new_file_id = self.upload_document(
                        item, store
                    )

                    old_file_id = (
                        previous.get("openai_file_id")
                        if previous else None
                    )

                    # Registrar primero la nueva versión.
                    docs[drive_id] = {
                        "name": item["name"],
                        "modified_time": item.get(
                            "modifiedTime"
                        ),
                        "mime_type": item["mimeType"],
                        "openai_file_id": new_file_id,
                        "url": self.document_url(
                            item, drive_id
                        )
                    }

                    self.save_manifest(manifest)

                    stats[
                        "updated" if previous else "added"
                    ] += 1

                    # Retirar la versión anterior
                    # después de guardar la nueva.
                    if (
                        old_file_id
                        and old_file_id != new_file_id
                    ):
                        try:
                            self.client.vector_stores.files.delete(
                                vector_store_id=store,
                                file_id=old_file_id
                            )
                        except Exception as exc:
                            stats["errors"].append({
                                "file": item["name"],
                                "error": (
                                    "Nueva versión indexada, "
                                    "pero no se pudo retirar "
                                    "la anterior: " + str(exc)
                                )
                            })

                except Exception as exc:
                    stats["errors"].append({
                        "file": item["name"],
                        "error": str(exc)
                    })

            # Retirar documentos eliminados de Drive.
            for drive_id in (
                set(docs) - set(eligible)
            ):

                try:
                    file_id = docs[drive_id][
                        "openai_file_id"
                    ]

                    self.client.vector_stores.files.delete(
                        vector_store_id=store,
                        file_id=file_id
                    )

                    del docs[drive_id]

                    self.save_manifest(manifest)

                    stats["removed"] += 1

                except Exception as exc:
                    stats["errors"].append({
                        "file": drive_id,
                        "error": str(exc)
                    })

            return {
                "vector_store_id": store,
                "stats": stats,
                "documents": list(docs.values())
            }

        finally:
            _LOCK.release()
