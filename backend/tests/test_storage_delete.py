from app.services import storage


def test_delete_object_local_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    key = "books/x/pages/y/v001.png"
    (tmp_path / "books/x/pages/y").mkdir(parents=True)
    (tmp_path / key).write_bytes(b"png")
    assert storage.exists(key)
    storage.delete_object(key)
    assert not storage.exists(key)
    # second delete must not raise
    storage.delete_object(key)
