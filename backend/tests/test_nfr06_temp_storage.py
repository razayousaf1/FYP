import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("OCR_ENGINE", "mock")
os.environ.setdefault("STORAGE_BACKEND", "local")

from shared.cloud_storage import temporary_upload, LOCAL_TEMP_DIR


def test_temp_file_created_then_deleted_on_success():
    with temporary_upload(b"test bytes", "doc.jpg") as path:
        assert os.path.exists(path)
        created_path = path
    assert not os.path.exists(created_path)


def test_temp_file_deleted_even_if_exception_occurs():
    """NFR-06: cleanup must happen even when processing fails partway
    through, not just on the success path."""
    captured_path = None
    try:
        with temporary_upload(b"test bytes", "doc.jpg") as path:
            captured_path = path
            raise RuntimeError("simulated processing failure")
    except RuntimeError:
        pass
    assert not os.path.exists(captured_path)


def test_temp_dir_ends_up_empty_after_multiple_requests():
    for i in range(5):
        with temporary_upload(f"content {i}".encode(), f"doc{i}.jpg"):
            pass
    assert os.listdir(LOCAL_TEMP_DIR) == []