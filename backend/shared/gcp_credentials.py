# -*- coding: utf-8 -*-
"""
Contract.AI - Shared Google Cloud credential handling
======================================================
One place that decides how Vision, Firestore and Firebase Storage
authenticate, so every module behaves the same way.

    On your Mac:
        GOOGLE_APPLICATION_CREDENTIALS (set in .env) points at the service
        account JSON key. It is checked and used exactly as before.

    On Google Cloud Run:
        GOOGLE_APPLICATION_CREDENTIALS is NOT set. Every Google client
        (Vision, Firestore, Storage) then uses the Cloud Run service
        account automatically - no key file inside the container.
"""
import os


def get_credentials_path():
    """
    Returns the service account key path if one is configured, or None
    when running on Cloud Run (where the built-in service account is used).

    Raises RuntimeError if the variable IS set but the file doesn't exist,
    because that is always a configuration mistake worth surfacing clearly.
    """
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        return None

    if not os.path.exists(creds_path):
        raise RuntimeError(
            f"GOOGLE_APPLICATION_CREDENTIALS points to a file that doesn't exist: "
            f"'{creds_path}'. Double-check the path in your .env file."
        )
    return creds_path


def init_firebase():
    """
    Initializes the Firebase Admin SDK once per process, with the SAME
    settings no matter which module (history_store.py or cloud_storage.py)
    happens to call it first. This includes the storage bucket, so Firebase
    Storage always works even if Firestore was initialized first.
    """
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return

    creds_path = get_credentials_path()
    if creds_path:
        cred = credentials.Certificate(creds_path)
    else:
        cred = credentials.ApplicationDefault()

    options = {}

    bucket = os.environ.get("FIREBASE_STORAGE_BUCKET")
    if bucket:
        options["storageBucket"] = bucket

    # Optional: only needed if Firestore ever can't detect the project on its own
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project_id:
        options["projectId"] = project_id

    firebase_admin.initialize_app(cred, options or None)