
"""Backend FastAPI del Agente Documental TIC."""

from pathlib import Path
from ipaddress import ip_address

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from openai import OpenAI

from app.core.config import settings
from app.models.documento import AskRequest, AskResponse
from app.services.sync_service import SyncService
from app.services.agent_service import AgentService


ROOT = Path(__file__).resolve().parents[1]

app = FastAPI(
    title="Archivo TIC IA",
    version="1.0.0"
)

# Permitir el frontend de GitHub Pages.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://yamishi-aymr.github.io",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Recursos estáticos.
app.mount(
    "/assets",
    StaticFiles(directory=ROOT / "assets"),
    name="assets"
)


# --------------------------------------------------
# SEGURIDAD: SINCRONIZACIÓN SOLO LOCAL
# --------------------------------------------------

def local_only(request: Request):
    """Evita sincronizaciones públicas no autorizadas."""

    host = request.client.host if request.client else ""

    try:
        if not ip_address(host).is_loopback:
            raise ValueError()
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail="Sincronización disponible solo desde localhost"
        )

    key = settings.local_admin_key

    if key and request.headers.get("X-Admin-Key") != key:
        raise HTTPException(
            status_code=401,
            detail="Clave administrativa incorrecta"
        )


# --------------------------------------------------
# INTERFAZ
# --------------------------------------------------

@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")


# --------------------------------------------------
# ESTADO DEL SERVIDOR
# --------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "configured": bool(
            settings.openai_api_key
            and settings.drive_folder_id
        )
    }


# --------------------------------------------------
# DOCUMENTOS INDEXADOS
# --------------------------------------------------

@app.get("/api/documents")
def documents():

    manifest = SyncService.load_manifest()

    store_id = (
        settings.vector_store_id
        or manifest.get("vector_store_id")
    )

    if not store_id:
        return {
            "documents": [],
            "indexed": 0,
            "vector_store_configured": False
        }

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Falta configurar OPENAI_API_KEY"
        )

    try:
        client = OpenAI(
            api_key=settings.openai_api_key
        )

        # Metadatos de los documentos locales.
        local_docs = manifest.get("documents", {})

        by_file_id = {
            doc["openai_file_id"]: doc
            for doc in local_docs.values()
            if doc.get("openai_file_id")
        }

        documents_list = []

       
        indexed_files = client.vector_stores.files.list(
            vector_store_id=store_id,
            limit=100
        )

        for item in indexed_files:

            # Evitar mostrar archivos no indexados.
            if item.status != "completed":
                continue

            file_id = item.id
            local = by_file_id.get(file_id)

            if local:
                name = local.get("name", "Documento")
                url = local.get("url", "")
                mime_type = local.get("mime_type", "")
            else:
                # Recuperar el nombre desde OpenAI.
                file_info = client.files.retrieve(file_id)

                name = file_info.filename
                url = ""
                mime_type = ""

            documents_list.append({
                "name": name,
                "url": url,
                "mime_type": mime_type,
                "openai_file_id": file_id
            })

        documents_list.sort(
            key=lambda doc: doc["name"].lower()
        )

        return {
            "documents": documents_list,
            "indexed": len(documents_list),
            "vector_store_configured": True
        }

  
    except Exception as exc:
        import traceback

        print(
            "\nERROR AL CONSULTAR DOCUMENTOS:",
            repr(exc),
            flush=True
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=502,
            detail="No se pudo consultar el índice documental de OpenAI."
        )


# --------------------------------------------------
# CONSULTAR AL AGENTE
# --------------------------------------------------

@app.post(
    "/api/ask",
    response_model=AskResponse
)
def ask(payload: AskRequest):

    try:
        if not settings.openai_api_key:
            raise ValueError("Falta OPENAI_API_KEY")

        return AgentService().ask(
            payload.question,
            payload.use_search
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Error al consultar OpenAI. Revisa los registros."
        )


# --------------------------------------------------
# SINCRONIZACIÓN LOCAL
# --------------------------------------------------

@app.post(
    "/api/sync",
    dependencies=[Depends(local_only)]
)
def sync():

    try:
        if not settings.openai_api_key:
            raise ValueError("Falta OPENAI_API_KEY")

        return SyncService().sync()

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Sincronización fallida: {exc}"
        )
