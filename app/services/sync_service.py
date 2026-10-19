
"""
Sincronización Google Drive -> OpenAI Vector Store.

Utiliza los atributos del Vector Store para
identificar archivos entre ejecuciones.

Permite una simulación segura antes de sincronizar.
"""

import json
import os
import threading
from pathlib import Path

from openai import OpenAI

from app.core.config import settings
from app.services.drive_service import DriveService


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "manifest.json"

_LOCK = threading.Lock()

SUPPORTED = {
    "application/pdf",
    "text/plain",
    "application/vnd.google-apps.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class SyncService:

    def __init__(self, client=None, drive=None):
        self.client = client or OpenAI(
            api_key=settings.openai_api_key
        )
        self.drive = drive or DriveService()

    @staticmethod
    def load_manifest():
        if not MANIFEST.exists():
            return {
                "vector_store_id": "",
                "documents": {}
            }

        return json.loads(
            MANIFEST.read_text(encoding="utf-8")
        )

    @staticmethod
    def save_manifest(data):
        MANIFEST.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        temp = MANIFEST.with_suffix(".tmp")

        temp.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        os.replace(temp, MANIFEST)

    def get_store(self, manifest, create=False):
        store = (
            settings.vector_store_id
            or manifest.get("vector_store_id")
        )

        if not store:
            if not create:
                raise ValueError(
                    "Falta VECTOR_STORE_ID. "
                    "No se creará otro índice automáticamente."
                )

            store = self.client.vector_stores.create(
                name="Archivo TIC IA - Documentos"
            ).id

        manifest["vector_store_id"] = store
        return store

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
                + drive_id + "/edit"
            )

        return (
            "https://drive.google.com/file/d/"
            + drive_id + "/view"
        )

    @staticmethod
    def filename_for(item):
        name = item["name"]

        if (
            item["mimeType"]
            == "application/vnd.google-apps.document"
        ):
            name += ".txt"

        return name.replace(
            "/", "_"
        ).replace("\\", "_")

    def indexed_documents(self, store):
        """
        Obtiene todos los archivos y sus atributos.
        Rechaza duplicados o atributos incompletos.
        """

        result = self.client.vector_stores.files.list(
            vector_store_id=store,
            limit=100
        )

        indexed = {}

        for file in result:
            if file.status != "completed":
                raise RuntimeError(
                    "Hay archivos con indexación incompleta. "
                    "Revisa el Vector Store antes de continuar."
                )

            attrs = file.attributes or {}
            drive_id = attrs.get("drive_id")

            if not drive_id or not attrs.get("modified_time"):
                raise RuntimeError(
                    "El archivo " + file.id
                    + " no tiene metadatos completos. "
                    "No se realizará la sincronización."
                )

            if drive_id in indexed:
                raise RuntimeError(
                    "Se encontraron archivos duplicados "
                    "para un mismo ID de Google Drive."
                )

            indexed[drive_id] = {
                "file_id": file.id,
                "attributes": attrs
            }

        return indexed

    def build_plan(self, source, indexed):
        """
        Compara Google Drive con OpenAI sin
        modificar ninguno de los dos servicios.
        """

        eligible = {
            item["id"]: item
            for item in source
            if item["mimeType"] in SUPPORTED
        }

        if not eligible:
            raise RuntimeError(
                "La carpeta no devolvió documentos "
                "compatibles. Se cancela la operación."
            )

        plan = {
            "added": [],
            "updated": [],
            "unchanged": [],
            "removed": []
        }

        for drive_id, item in eligible.items():
            previous = indexed.get(drive_id)

            if previous is None:
                plan["added"].append(item)
                continue

            attrs = previous["attributes"]

            changed = (
                attrs.get("modified_time")
                != item.get("modifiedTime")
                or attrs.get("name")
                != item.get("name")
            )

            if changed:
                plan["updated"].append(item)
            else:
                plan["unchanged"].append(item)

        for drive_id in set(indexed) - set(eligible):
            plan["removed"].append(drive_id)

        return plan

    def preview(self):
        """
        Simulación de solo lectura.
        No sube, actualiza ni elimina archivos.
        """

        manifest = self.load_manifest()
        store = self.get_store(manifest)

        indexed = self.indexed_documents(store)

        source = self.drive.list_files(
            settings.drive_folder_id
        )

        plan = self.build_plan(source, indexed)

        return {
            "vector_store_id": store,
            "added": [
                item["name"]
                for item in plan["added"]
            ],
            "updated": [
                item["name"]
                for item in plan["updated"]
            ],
            "unchanged": [
                item["name"]
                for item in plan["unchanged"]
            ],
            "removed": plan["removed"]
        }

    def upload_document(self, item, store):
        raw, filename, _ = self.drive.get_bytes(item)

        if not raw:
            raise ValueError("El archivo está vacío")

        filename = filename.replace(
            "/", "_"
        ).replace("\\", "_")

        attrs = {
            "drive_id": item["id"],
            "modified_time": item.get(
                "modifiedTime", ""
            ),
            "name": item["name"],
            "drive_url": self.document_url(
                item, item["id"]
            )
        }

        upload = self.client.vector_stores.files.upload_and_poll(
            vector_store_id=store,
            file=(filename, raw),
            attributes=attrs
        )

        if upload.status != "completed":
            raise RuntimeError(
                "Indexación no completada: "
                + upload.status
            )

        return upload.id

    def sync(self):
        """
        Sincroniza archivos nuevos y modificados.

        Por seguridad, NO elimina automáticamente
        archivos ausentes de Google Drive.
        """

        if not _LOCK.acquire(blocking=False):
            raise RuntimeError(
                "Ya existe una sincronización en curso."
            )

        try:
            manifest = self.load_manifest()
            store = self.get_store(manifest)

            indexed = self.indexed_documents(store)

            source = self.drive.list_files(
                settings.drive_folder_id
            )

            plan = self.build_plan(source, indexed)

            stats = {
                "added": 0,
                "updated": 0,
                "removed": 0,
                "unchanged": len(plan["unchanged"]),
                "errors": []
            }

            docs = manifest.setdefault(
                "documents", {}
            )

            for action in ("added", "updated"):
                for item in plan[action]:
                    drive_id = item["id"]
                    previous = indexed.get(drive_id)

                    try:
                        new_id = self.upload_document(
                            item, store
                        )

                        docs[drive_id] = {
                            "name": item["name"],
                            "modified_time": item.get(
                                "modifiedTime"
                            ),
                            "mime_type": item["mimeType"],
                            "openai_file_id": new_id,
                            "url": self.document_url(
                                item, drive_id
                            )
                        }

                        self.save_manifest(manifest)

                        stats[action] += 1

                        if previous:
                            old_id = previous["file_id"]

                            if old_id != new_id:
                                try:
                                    self.client.vector_stores.files.delete(
                                        vector_store_id=store,
                                        file_id=old_id
                                    )
                                except Exception as exc:
                                    stats["errors"].append({
                                        "file": item["name"],
                                        "error": (
                                            "No se pudo retirar "
                                            "la versión antigua: "
                                            + str(exc)
                                        )
                                    })

                    except Exception as exc:
                        stats["errors"].append({
                            "file": item["name"],
                            "error": str(exc)
                        })

            if plan["removed"]:
                stats["errors"].append({
                    "warning": (
                        "Se detectaron documentos ausentes "
                        "en Drive, pero no se eliminaron."
                    ),
                    "drive_ids": plan["removed"]
                })

            return {
                "vector_store_id": store,
                "stats": stats,
                "documents": list(docs.values())
            }

        finally:
            _LOCK.release()
