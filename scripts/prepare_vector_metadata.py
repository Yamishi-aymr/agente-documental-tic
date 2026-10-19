
"""
Prepara los metadatos del Vector Store.

Por defecto solo muestra los cambios previstos.
Con --apply actualiza los atributos de OpenAI.
No sube ni elimina documentos.
"""

import argparse
from openai import OpenAI

from app.core.config import settings
from app.services.sync_service import SyncService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true"
    )
    args = parser.parse_args()

    manifest = SyncService.load_manifest()

    store_id = (
        settings.vector_store_id
        or manifest.get("vector_store_id")
    )

    if not store_id:
        raise RuntimeError(
            "No se encontró VECTOR_STORE_ID."
        )

    client = OpenAI(
        api_key=settings.openai_api_key
    )

    documents = manifest.get("documents", {})

    print("Documentos registrados:", len(documents))

    for drive_id, doc in documents.items():
        file_id = doc["openai_file_id"]

        attributes = {
            "drive_id": drive_id,
            "modified_time": doc.get(
                "modified_time", ""
            ),
            "name": doc.get("name", ""),
            "drive_url": doc.get("url", "")
        }

        # Comprobar que el archivo existe
        # en el Vector Store.
        current = client.vector_stores.files.retrieve(
            file_id=file_id,
            vector_store_id=store_id
        )

        print(
            f"\nArchivo: {doc['name']}"
            f"\nEstado: {current.status}"
        )

        if current.status != "completed":
            print("Omitido: indexación incompleta.")
            continue

        if not args.apply:
            print("Vista previa: se agregarían atributos.")
            continue

        existing = current.attributes or {}
        merged = {
            **existing,
            **attributes
        }

        client.vector_stores.files.update(
            file_id=file_id,
            vector_store_id=store_id,
            attributes=merged
        )

        print("Metadatos actualizados.")

    print("\nProceso finalizado.")


if __name__ == "__main__":
    main()
