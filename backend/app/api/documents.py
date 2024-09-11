from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.collections import get_readable_collection
from app.api.deps import DB, AdminUser, CurrentUser
from app.models import Chunk, Collection, Document, DocumentVersion, User, VersionStatus
from app.schemas.knowledge import ChunkOut, DocumentDetail, DocumentOut, UploadResult, VersionOut
from app.services import ingestion, storage
from app.services.ingestion import MAX_UPLOAD_BYTES, UploadRejected
from app.services.permissions import readable_collection_ids

router = APIRouter(prefix="/api", tags=["documents"])


def _latest(doc: Document) -> DocumentVersion | None:
    return doc.versions[0] if doc.versions else None


def _out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        collection_id=doc.collection_id,
        title=doc.title,
        filename=doc.filename,
        created_at=doc.created_at,
        current_version=VersionOut.model_validate(doc.current_version)
        if doc.current_version
        else None,
        latest_version=VersionOut.model_validate(_latest(doc)) if doc.versions else None,
    )


def get_readable_document(db: Session, user: User, document_id: int) -> Document:
    doc = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.deleted_at.is_(None),
            Document.collection_id.in_(readable_collection_ids(user)),
        )
    )
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


async def _read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Files must be 2 MB or smaller")
    return data


def _upload(
    db: Session,
    user: User,
    collection: Collection,
    filename: str,
    data: bytes,
    title: str | None,
    document: Document | None = None,
) -> UploadResult:
    try:
        doc, version, created = ingestion.create_version(
            db,
            collection=collection,
            filename=filename,
            data=data,
            user=user,
            title=title,
            document=document,
        )
    except UploadRejected as e:
        raise HTTPException(422, str(e)) from None
    queued = ingestion.enqueue(version.id) if created else False
    db.expire_all()
    doc = db.get(Document, doc.id)
    return UploadResult(
        document=_out(doc),
        version=VersionOut.model_validate(db.get(DocumentVersion, version.id)),
        created=created,
        queued=queued,
    )


@router.get("/collections/{collection_id}/documents", response_model=list[DocumentOut])
def list_documents(collection_id: int, db: DB, user: CurrentUser) -> list[DocumentOut]:
    get_readable_collection(db, user, collection_id)
    docs = db.scalars(
        select(Document)
        .where(Document.collection_id == collection_id, Document.deleted_at.is_(None))
        .order_by(Document.title)
    )
    return [_out(d) for d in docs]


@router.post("/collections/{collection_id}/documents", response_model=UploadResult, status_code=201)
async def upload_document(
    collection_id: int,
    db: DB,
    user: AdminUser,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
) -> UploadResult:
    collection = db.get(Collection, collection_id)
    if not collection:
        raise HTTPException(404, "Collection not found")
    data = await _read_upload(file)
    return _upload(db, user, collection, file.filename or "upload.txt", data, title)


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: DB, user: CurrentUser) -> DocumentDetail:
    doc = get_readable_document(db, user, document_id)
    return DocumentDetail(
        **_out(doc).model_dump(),
        collection_name=doc.collection.name,
        versions=[VersionOut.model_validate(v) for v in doc.versions],
    )


@router.post("/documents/{document_id}/versions", response_model=UploadResult, status_code=201)
async def upload_version(
    document_id: int, db: DB, user: AdminUser, file: Annotated[UploadFile, File()]
) -> UploadResult:
    doc = get_readable_document(db, user, document_id)
    data = await _read_upload(file)
    return _upload(db, user, doc.collection, doc.filename, data, None, document=doc)


@router.post("/documents/{document_id}/versions/{version_id}/reprocess", response_model=VersionOut)
def reprocess_version(
    document_id: int, version_id: int, db: DB, user: AdminUser
) -> DocumentVersion:
    get_readable_document(db, user, document_id)
    version = db.get(DocumentVersion, version_id)
    if not version or version.document_id != document_id:
        raise HTTPException(404, "Version not found")
    if version.status in (VersionStatus.queued, VersionStatus.processing):
        raise HTTPException(409, "This version is already being processed")
    if version.status == VersionStatus.failed:
        version.status, version.stage, version.progress = VersionStatus.queued, "queued", 0
    db.commit()
    ingestion.enqueue(version.id)
    db.refresh(version)
    return version


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: int, db: DB, user: AdminUser) -> None:
    ingestion.delete_document(db, get_readable_document(db, user, document_id))


@router.get("/documents/{document_id}/versions/{version_id}/download")
def download_version(
    document_id: int, version_id: int, db: DB, user: CurrentUser
) -> dict[str, str]:
    doc = get_readable_document(db, user, document_id)
    version = db.get(DocumentVersion, version_id)
    if not version or version.document_id != doc.id:
        raise HTTPException(404, "Version not found")
    name = doc.filename.rsplit(".", 1)
    filename = f"{name[0]}-v{version.version}.{name[1]}" if len(name) == 2 else doc.filename
    return {"url": storage.presigned_get(version.s3_key, filename)}


@router.get("/documents/{document_id}/versions/{version_id}/chunks", response_model=list[ChunkOut])
def list_chunks(document_id: int, version_id: int, db: DB, user: CurrentUser) -> list[Chunk]:
    get_readable_document(db, user, document_id)
    q = select(Chunk).where(Chunk.document_id == document_id, Chunk.version_id == version_id)
    return list(db.scalars(q.order_by(Chunk.ordinal)))
