import os
import uuid
import logging
from contextlib import contextmanager

from shared.gcp_credentials import init_firebase

logger = logging.getLogger("contract_ai")

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")

LOCAL_TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_uploads")
os.makedirs(LOCAL_TEMP_DIR, exist_ok=True)

FIREBASE_STORAGE_BUCKET = os.environ.get("FIREBASE_STORAGE_BUCKET")
_firebase_initialized = False


def _ensure_firebase_initialized():
    """Lazily initializes the Firebase Admin SDK. Mirrors the same
    lazy-init pattern used in ocr_engine.py and history_store.py.

    Credentials come from shared/gcp_credentials.py: the key file from .env
    locally, or the Cloud Run service account when deployed."""
    global _firebase_initialized
    if not _firebase_initialized:
        if not FIREBASE_STORAGE_BUCKET:
            raise RuntimeError(
                "FIREBASE_STORAGE_BUCKET is not set. Add it to .env, e.g.:\n"
                "  FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com"
            )

        init_firebase()
        _firebase_initialized = True


@contextmanager
def temporary_upload(file_bytes: bytes, filename: str):
    """
    NFR-06: makes file_bytes available at a path/reference for the
    duration of the `with` block, then deletes it - guaranteed, even if
    processing raises an exception.

    Yields a local file path (both backends yield something path-like;
    for "firebase" it's the Storage blob path, not usable as a real
    local file path - callers in this codebase don't currently need to
    open the yielded value themselves, since extract_text() works on the
    original in-memory bytes, not this path. This context manager exists
    purely to demonstrate/enforce the NFR-06 write-then-delete lifecycle.)
    """
    if STORAGE_BACKEND == "local":
        ext = os.path.splitext(filename)[1]
        temp_path = os.path.join(LOCAL_TEMP_DIR, f"{uuid.uuid4().hex}{ext}")
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
        logger.info(f"NFR-06: temporarily stored upload at {temp_path} for processing")
        try:
            yield temp_path
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"NFR-06: deleted temporary upload {temp_path} (processing complete)")

    elif STORAGE_BACKEND == "firebase":
        _ensure_firebase_initialized()
        from firebase_admin import storage

        bucket = storage.bucket()
        blob_path = f"temp_uploads/{uuid.uuid4().hex}_{filename}"
        blob = bucket.blob(blob_path)

        blob.upload_from_string(file_bytes, content_type="application/octet-stream")
        logger.info(f"NFR-06: uploaded to Firebase Storage at {blob_path} for processing")
        try:
            yield blob_path
        finally:
            try:
                blob.delete()
                logger.info(f"NFR-06: deleted from Firebase Storage: {blob_path} (processing complete)")
            except Exception as e:
                logger.warning(f"NFR-06: failed to delete Firebase Storage blob {blob_path}: {e}")

    else:
        raise RuntimeError(f"Unknown STORAGE_BACKEND '{STORAGE_BACKEND}'. Use 'local' or 'firebase'.")