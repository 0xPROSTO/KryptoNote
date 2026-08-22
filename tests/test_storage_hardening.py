import base64
import os
import sqlite3
from types import SimpleNamespace

import pytest
from cryptography.exceptions import InvalidTag

from KryptoNote.core.crypto import CryptoManager
from KryptoNote.core.constants import MEDIA_CHUNK_SIZE
from KryptoNote.core.database import (
    DatabaseConnection,
    NodeRepository,
    acquire_database_session_lock,
    try_acquire_database_session_lock,
    write_chunked_media,
)
from KryptoNote.core.exceptions import ProjectInUseError
from KryptoNote.gui.services.media_export_service import (
    MediaExportService,
    MediaExportWorker,
)
from KryptoNote.services.auth_service import AuthService
from KryptoNote.services.export_service import MarkdownExportService
from KryptoNote.services.graph_export_service import GraphExportService
from KryptoNote.services.node_service import NodeService
from KryptoNote.services.password_change_service import PasswordChangeService


def test_authenticated_reopen_holds_session_lock_until_connection_close(tmp_path):
    database_path = tmp_path / "locked-project.zrx"
    database = DatabaseConnection(str(database_path))
    crypto = CryptoManager()
    AuthService.initialize_v3_project(database, crypto, "correct horse battery staple")
    database.close()

    session_lock = acquire_database_session_lock(str(database_path))
    reopened = AuthService.reopen_authenticated_database(
        str(database_path), crypto.create_clone(), session_lock
    )
    assert try_acquire_database_session_lock(str(database_path)) is None
    reopened.close()

    next_lock = try_acquire_database_session_lock(str(database_path))
    assert next_lock is not None
    next_lock.release()

    wrong_crypto = CryptoManager()
    wrong_crypto.load_data_key(bytes(reversed(range(32))))
    failed_lock = acquire_database_session_lock(str(database_path))
    with pytest.raises(InvalidTag):
        AuthService.reopen_authenticated_database(
            str(database_path), wrong_crypto, failed_lock
        )
    assert failed_lock.acquired
    failed_lock.release()


def test_project_deletion_refuses_an_open_session(tmp_path):
    from KryptoNote.gui.widgets.launcher import ProjectLauncher

    database_path = tmp_path / "open-project.zrx"
    database = DatabaseConnection(str(database_path))
    database.close()
    session_lock = acquire_database_session_lock(str(database_path))
    try:
        with pytest.raises(ProjectInUseError):
            ProjectLauncher._remove_project_files(str(database_path))
        assert database_path.exists()
    finally:
        session_lock.release()

    ProjectLauncher._remove_project_files(str(database_path))
    assert not database_path.exists()


def test_corrupt_encrypted_tag_is_reported_in_all_repository_reads():
    database = DatabaseConnection(":memory:")
    crypto = CryptoManager()
    crypto.load_data_key(bytes(range(32)))
    repository = NodeRepository(database, crypto)
    try:
        item_id = repository.add_item("text", 0, 0, 200, 120, title="Tagged")
        tag_id = repository.ensure_tag("evidence", "#336699")
        repository.set_item_tag(item_id, tag_id, True)
        database.conn.execute(
            "UPDATE tags SET name=? WHERE id=?",
            (b"broken", tag_id),
        )
        database.conn.commit()

        with pytest.raises(sqlite3.DatabaseError, match=f"Tag {tag_id}"):
            repository.get_all_tags()
        with pytest.raises(sqlite3.DatabaseError, match=f"Tag {tag_id}"):
            repository.get_item_tags(item_id)
        with pytest.raises(sqlite3.DatabaseError, match=f"Tag {tag_id}"):
            repository.build_graph_copy_blueprint([item_id])
        with pytest.raises(sqlite3.DatabaseError, match=f"Tag {tag_id}"):
            GraphExportService(":memory:", crypto).build_graph(database.conn)
    finally:
        repository.close()
        database.close()


def test_failed_media_export_preserves_existing_destination(tmp_path):
    destination = tmp_path / "evidence.bin"
    destination.write_bytes(b"original destination")

    class IncompleteChunkService:
        @staticmethod
        def get_item_info(_node_id):
            return SimpleNamespace(is_chunked=True, total_size=10)

        @staticmethod
        def get_chunk(_node_id, _index):
            return b"short"

    with pytest.raises(OSError, match="Incomplete export"):
        MediaExportService(IncompleteChunkService()).export_node(7, destination)

    assert destination.read_bytes() == b"original destination"
    assert list(tmp_path.glob(".kryptonote-*.part")) == []


def test_media_export_worker_uses_separate_database_and_replaces_atomically(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "media-project.zrx"
    destination = tmp_path / "exported.bin"
    destination.write_bytes(b"old")
    payload = b"decrypted media payload"

    database = DatabaseConnection(str(database_path))
    crypto = CryptoManager()
    crypto.load_data_key(bytes(range(32)))
    repository = NodeRepository(database, crypto)
    try:
        item_id = repository.add_item(
            "image",
            0,
            0,
            320,
            180,
            title="evidence.bin",
            data=payload,
            original_filename="evidence.bin",
        )
    finally:
        repository.close()
        database.close()

    def reject_materialized_legacy_read(*_args, **_kwargs):
        raise AssertionError("legacy media export must use streaming reads")

    monkeypatch.setattr(
        NodeRepository, "get_full_data", reject_materialized_legacy_read
    )
    completed = []
    failures = []
    worker = MediaExportWorker(
        str(database_path), crypto.create_clone(), item_id, str(destination)
    )
    worker.finished.connect(completed.append)
    worker.failed.connect(failures.append)
    worker.run()

    assert failures == []
    assert completed == [str(destination)]
    assert destination.read_bytes() == payload
    assert list(tmp_path.glob(".kryptonote-*.part")) == []


def test_graph_export_streams_legacy_media_and_keeps_unrelated_part(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "graph-project.zrx"
    database = DatabaseConnection(str(database_path))
    crypto = CryptoManager()
    crypto.load_data_key(bytes(range(32)))
    repository = NodeRepository(database, crypto)
    payload = b"\x89PNG\r\n\x1a\nlegacy payload"
    try:
        item_id = repository.add_item(
            "image",
            0,
            0,
            320,
            180,
            title="legacy-image",
            data=payload,
        )
    finally:
        repository.close()
        database.close()

    full_data_aad = crypto.item_aad(item_id, "full_data")
    decrypt = crypto.decrypt

    def reject_materialized_full_data(value, aad=None):
        if aad == full_data_aad:
            raise AssertionError("graph export must stream legacy full_data")
        return decrypt(value, aad=aad)

    monkeypatch.setattr(crypto, "decrypt", reject_materialized_full_data)

    destination = tmp_path / "graph.html"
    old_fixed_part = tmp_path / "graph.html.part"
    old_fixed_part.write_bytes(b"unrelated file")

    GraphExportService(str(database_path), crypto).export(destination, "html")

    html = destination.read_text(encoding="utf-8")
    assert "<!doctype html>" in html.lower()
    assert base64.b64encode(payload).decode("ascii") in html
    assert old_fixed_part.read_bytes() == b"unrelated file"
    assert list(tmp_path.glob(".kryptonote-*.part")) == []


def test_exporters_refuse_to_replace_the_open_database(tmp_path):
    database_path = tmp_path / "live-project.zrx"
    database = DatabaseConnection(str(database_path))
    crypto = CryptoManager()
    crypto.load_data_key(bytes(range(32)))
    repository = NodeRepository(database, crypto)
    try:
        item_id = repository.add_item(
            "image",
            0,
            0,
            100,
            100,
            title="evidence.bin",
            data=b"evidence",
        )
        service = NodeService(repository)
        items = service.get_all_items()

        with pytest.raises(ValueError, match="cannot overwrite"):
            MediaExportService(service).export_node(item_id, database_path)
        with pytest.raises(ValueError, match="cannot overwrite"):
            GraphExportService(str(database_path), crypto).export(
                database_path, "html"
            )
        with pytest.raises(ValueError, match="cannot overwrite"):
            MarkdownExportService().export(
                items,
                [],
                str(database_path),
                database_path=str(database_path),
            )

        assert repository.get_item_info(item_id) is not None
        assert database.conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        repository.close()
        database.close()


def test_password_change_preserves_valid_kdf_parameters(tmp_path):
    database_path = tmp_path / "password-project.zrx"
    database = DatabaseConnection(str(database_path))
    data_key = bytes(range(32))
    crypto = CryptoManager()
    crypto.load_data_key(data_key)
    params = {"iterations": 2, "memory_cost": 8 * 1024, "lanes": 1}
    salt = os.urandom(16)
    password_key = CryptoManager.derive_password_key(
        "old password", salt, **params
    )
    metadata = {
        "crypto_version": "3",
        "auth_salt": salt,
        "wrapped_data_key": CryptoManager.wrap_data_key(data_key, password_key),
        "auth_check": crypto.encrypt(
            AuthService.AUTH_CHECK_PLAINTEXT,
            aad=crypto.auth_check_aad(),
        ),
        "kdf_name": CryptoManager.KDF_NAME,
        "kdf_iterations": str(params["iterations"]),
        "kdf_memory_cost": str(params["memory_cost"]),
        "kdf_lanes": str(params["lanes"]),
    }
    for key, value in metadata.items():
        database.set_metadata(key, value, commit=False)
    database.conn.commit()
    database.close()

    results = []
    PasswordChangeService.change_password(
        str(database_path),
        "old password",
        "new password",
        on_finished=lambda success, message: results.append((success, message)),
    )
    assert results and results[-1][0]

    reopened = DatabaseConnection(
        str(database_path), initialize=False, must_exist=True, writable=False
    )
    try:
        assert AuthService.read_kdf_params(reopened) == params
        new_salt = reopened.get_metadata("auth_salt")
        wrapped_data_key = reopened.get_metadata("wrapped_data_key")
        new_password_key = CryptoManager.derive_password_key(
            "new password", new_salt, **params
        )
        assert CryptoManager.unwrap_data_key(
            wrapped_data_key, new_password_key
        ) == data_key
    finally:
        reopened.close()


def test_chunked_writer_rejects_noncanonical_chunk_size(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"payload")
    database = DatabaseConnection(":memory:")
    crypto = CryptoManager()
    crypto.load_data_key(bytes(range(32)))
    try:
        with pytest.raises(ValueError, match="MEDIA_CHUNK_SIZE"):
            write_chunked_media(
                database.cursor,
                database.conn,
                crypto,
                "video",
                0,
                0,
                100,
                100,
                "video",
                None,
                str(source),
                MEDIA_CHUNK_SIZE // 2,
            )
        assert database.conn.execute(
            "SELECT COUNT(*) FROM items"
        ).fetchone()[0] == 0
    finally:
        database.close()
