import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.core.config import get_settings
from app.core.embeddings import EmbeddingProvider, get_embeddings
from app.core.errors import ProblemError
from app.core.tenancy import CurrentUserDep, OwnerDep, TenantDB
from app.modules.documents import service
from app.modules.documents.schemas import DocumentOut

router = APIRouter(prefix="/documents", tags=["documentos del asistente"])
Embeddings = Annotated[EmbeddingProvider, Depends(get_embeddings)]


@router.get("", response_model=list[DocumentOut])
def list_documents(_user: CurrentUserDep, db: TenantDB) -> list[DocumentOut]:
    return service.list_documents(db)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload(
    _owner: OwnerDep,
    db: TenantDB,
    emb: Embeddings,
    file: UploadFile = File(..., description="PDF, Excel (.xlsx), CSV o TXT"),  # noqa: B008
) -> DocumentOut:
    """Sube un documento (condiciones de proveedores, políticas, recetas escritas) para que el asistente
    pueda responder preguntas abiertas citándolo. Su contenido se trata como dato, nunca como instrucción."""
    max_bytes = get_settings().document_max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ProblemError(
            413, "file_too_large", "El documento es demasiado grande", f"El máximo es {max_bytes // 1048576} MB."
        )
    return service.upload(db, emb, file.filename or "documento", data)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(document_id: uuid.UUID, _owner: OwnerDep, db: TenantDB) -> None:
    """Borra el documento y todos sus fragmentos."""
    service.delete(db, document_id)
