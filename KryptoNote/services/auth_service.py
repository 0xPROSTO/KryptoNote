import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag

from ..core.crypto import CryptoManager
from ..core.database import DatabaseConnection, NodeRepository
from ..core.exceptions import AuthError, CryptoError, OperationCancelledError


class AuthService:
    """Handles project authentication and encryption migration."""

    AUTH_CHECK_PLAINTEXT = b"KryptoNote_Auth_OK"
    CRYPTO_VERSION = "2"

    @staticmethod
    def authenticate(db_path, password_provider, mode):
        from .node_service import NodeService

        if mode not in {"create", "open"}:
            raise ValueError(f"Unsupported authentication mode: {mode}")

        salt = None
        if mode == "open":
            try:
                salt = DatabaseConnection.read_metadata_readonly(
                    db_path,
                    "auth_salt",
                )
            except Exception as exc:
                raise AuthError("Corrupted database: unreadable metadata") from exc
            if not salt:
                raise AuthError("Corrupted database: missing authentication salt")

        db_conn = DatabaseConnection(db_path)
        try:
            crypto = CryptoManager()
            db_name = os.path.basename(db_path)

            if mode == "create":
                AuthService.create_new_password(
                    db_conn, crypto, db_name, password_provider
                )
            else:
                AuthService.verify_existing_password(
                    db_conn, crypto, salt, db_name, password_provider
                )

            repo = NodeRepository(db_conn, crypto)
            service = NodeService(repo)
            return db_conn, crypto, repo, service
        except Exception:
            try:
                db_conn.close()
            except Exception:
                pass
            raise

    @staticmethod
    def create_new_password(db_conn, crypto, db_name, provider):
        error_msg = None
        while True:
            pwd1, ok1 = provider("create", db_name, error_msg)
            if not ok1 or not pwd1:
                raise AuthError("Password entry cancelled")

            pwd2, ok2 = provider("confirm", db_name, None)
            if not ok2:
                raise AuthError("Password entry cancelled")

            if pwd1 == pwd2:
                AuthService.initialize_v2_project(db_conn, crypto, pwd1)
                return db_conn.get_salt()
            error_msg = "Passwords do not match"

    @staticmethod
    def verify_existing_password(db_conn, crypto, salt, db_name, provider):
        error_msg = None
        while True:
            pwd, ok = provider("enter", db_name, error_msg)
            if not ok or not pwd:
                raise AuthError("Password entry cancelled")

            try:
                AuthService.unlock_existing_database(db_conn, crypto, pwd, salt)
                return
            except InvalidTag:
                error_msg = "Incorrect password"
                continue

    @staticmethod
    def unlock_existing_database(
        db_conn,
        crypto,
        password,
        salt,
        before_legacy_migration=None,
        cancel_check=None,
        progress_callback=None,
    ):
        last_error = None
        is_v2 = AuthService.is_v2_database(db_conn)

        for candidate_salt in AuthService.salt_candidates(salt):
            try:
                if is_v2:
                    AuthService.unlock_v2_database(
                        db_conn, crypto, password, candidate_salt, cancel_check
                    )
                else:
                    AuthService.unlock_and_migrate_legacy(
                        db_conn,
                        crypto,
                        password,
                        candidate_salt,
                        before_migration=before_legacy_migration,
                        cancel_check=cancel_check,
                        progress_callback=progress_callback,
                    )

                if crypto.decrypt(db_conn.get_auth_check()) == AuthService.AUTH_CHECK_PLAINTEXT:
                    return
            except (InvalidTag, CryptoError, TypeError, ValueError) as exc:
                last_error = exc
                continue

        raise InvalidTag() from last_error

    @staticmethod
    def salt_candidates(salt):
        if isinstance(salt, str):
            candidates = []
            text = salt.strip()
            try:
                candidates.append(CryptoManager.normalize_salt(text))
            except CryptoError:
                pass
            encoded = text.encode("utf-8")
            if encoded not in candidates:
                candidates.append(encoded)
            return candidates

        normalized = CryptoManager.normalize_salt(salt)
        candidates = [normalized]
        try:
            text = bytes(normalized).decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""
        if text:
            try:
                uuid_salt = CryptoManager.normalize_salt(text)
                if uuid_salt not in candidates:
                    candidates.append(uuid_salt)
            except CryptoError:
                pass
        return candidates

    @staticmethod
    def is_v2_database(db_conn):
        try:
            version = db_conn.get_crypto_version()
        except Exception:
            version = 1
        return version == 2 or db_conn.get_wrapped_data_key() is not None

    @staticmethod
    def write_kdf_metadata(db_conn, commit=False):
        db_conn.set_metadata("kdf_name", CryptoManager.KDF_NAME, commit=False)
        db_conn.set_metadata("kdf_iterations", str(CryptoManager.KDF_ITERATIONS), commit=False)
        db_conn.set_metadata("kdf_memory_cost", str(CryptoManager.KDF_MEMORY_COST), commit=False)
        db_conn.set_metadata("kdf_lanes", str(CryptoManager.KDF_LANES), commit=False)
        if commit:
            db_conn.conn.commit()

    @staticmethod
    def read_kdf_params(db_conn):
        return AuthService.read_kdf_params_from_getter(db_conn.get_metadata)

    @staticmethod
    def read_kdf_params_from_getter(get_metadata):
        name = AuthService._metadata_text(get_metadata("kdf_name")) or CryptoManager.KDF_NAME
        if name.lower() != CryptoManager.KDF_NAME:
            raise AuthError(f"Unsupported KDF: {name}")
        return {
            "iterations": AuthService._metadata_int(
                get_metadata,
                "kdf_iterations",
                CryptoManager.KDF_ITERATIONS,
                CryptoManager.KDF_ITERATIONS_RANGE,
            ),
            "memory_cost": AuthService._metadata_int(
                get_metadata,
                "kdf_memory_cost",
                CryptoManager.KDF_MEMORY_COST,
                CryptoManager.KDF_MEMORY_COST_RANGE,
            ),
            "lanes": AuthService._metadata_int(
                get_metadata,
                "kdf_lanes",
                CryptoManager.KDF_LANES,
                CryptoManager.KDF_LANES_RANGE,
            ),
        }

    @staticmethod
    def _metadata_text(value):
        if value is None:
            return None
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise AuthError("Invalid KDF metadata encoding") from exc
        return str(value)

    @staticmethod
    def _metadata_int(get_metadata, key, default, valid_range):
        value = AuthService._metadata_text(get_metadata(key))
        if value in (None, ""):
            return default
        try:
            parsed = int(value)
        except ValueError as exc:
            raise AuthError(f"Invalid {key} metadata") from exc
        minimum, maximum = valid_range
        if not minimum <= parsed <= maximum:
            raise AuthError(
                f"Invalid {key} metadata: expected {minimum}..{maximum}"
            )
        return parsed

    @staticmethod
    def initialize_v2_project(db_conn, crypto, password, cancel_check=None):
        AuthService._raise_if_cancelled(cancel_check)
        salt = os.urandom(16)
        data_key = CryptoManager.generate_data_key()
        password_key = CryptoManager.derive_password_key(password, salt)
        AuthService._raise_if_cancelled(cancel_check)
        wrapped_data_key = CryptoManager.wrap_data_key(data_key, password_key)
        crypto.load_data_key(data_key)

        db_conn.set_metadata("auth_salt", salt, commit=False)
        db_conn.set_metadata("wrapped_data_key", wrapped_data_key, commit=False)
        db_conn.set_metadata(
            "auth_check",
            crypto.encrypt(AuthService.AUTH_CHECK_PLAINTEXT),
            commit=False,
        )
        db_conn.set_metadata("crypto_version", AuthService.CRYPTO_VERSION, commit=False)
        AuthService.write_kdf_metadata(db_conn, commit=False)
        db_conn.conn.commit()

    @staticmethod
    def unlock_v2_database(
        db_conn, crypto, password, salt, cancel_check=None
    ):
        wrapped_data_key = db_conn.get_wrapped_data_key()
        auth_check = db_conn.get_auth_check()
        if not wrapped_data_key:
            raise AuthError("Corrupted database: missing wrapped data key")
        if not auth_check:
            raise AuthError("Corrupted database: missing auth check")

        AuthService._raise_if_cancelled(cancel_check)
        kdf_params = AuthService.read_kdf_params(db_conn)
        password_key = CryptoManager.derive_password_key(password, salt, **kdf_params)
        AuthService._raise_if_cancelled(cancel_check)
        data_key = CryptoManager.unwrap_data_key(wrapped_data_key, password_key)
        crypto.load_data_key(data_key)

    @staticmethod
    def unlock_and_migrate_legacy(
        db_conn,
        crypto,
        password,
        salt,
        before_migration=None,
        cancel_check=None,
        progress_callback=None,
    ):
        AuthService._raise_if_cancelled(cancel_check)
        legacy_crypto = CryptoManager()
        legacy_crypto.derive_key(password, salt)
        AuthService._raise_if_cancelled(cancel_check)

        auth_check = db_conn.get_auth_check()
        if auth_check:
            if legacy_crypto.decrypt(auth_check) != AuthService.AUTH_CHECK_PLAINTEXT:
                raise InvalidTag()
        else:
            AuthService._verify_legacy_payload_decryptable(db_conn, legacy_crypto)

        if before_migration:
            before_migration()

        AuthService.migrate_legacy_to_v2(
            db_conn,
            legacy_crypto,
            crypto,
            password,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )

    @staticmethod
    def _verify_legacy_payload_decryptable(db_conn, legacy_crypto):
        found_blob = False
        last_error = None
        for blob in AuthService._iter_legacy_probe_blobs(db_conn):
            found_blob = True
            try:
                legacy_crypto.decrypt(blob)
                return
            except (InvalidTag, CryptoError, TypeError, ValueError) as exc:
                last_error = exc

        if found_blob:
            raise InvalidTag() from last_error

    @staticmethod
    def _iter_legacy_probe_blobs(db_conn):
        item_columns = AuthService._table_columns(db_conn, "items")
        for column in ("title", "text_content", "thumbnail", "full_data"):
            if column not in item_columns:
                continue
            db_conn.cursor.execute(
                f'SELECT "{column}" FROM items WHERE "{column}" IS NOT NULL ORDER BY id LIMIT 3'
            )
            for (blob,) in db_conn.cursor.fetchall():
                if blob:
                    yield blob

        chunk_columns = AuthService._table_columns(db_conn, "media_chunks")
        if "data" in chunk_columns:
            db_conn.cursor.execute(
                'SELECT "data" FROM media_chunks WHERE "data" IS NOT NULL ORDER BY id LIMIT 3'
            )
            for (blob,) in db_conn.cursor.fetchall():
                if blob:
                    yield blob

    @staticmethod
    def _table_columns(db_conn, table_name):
        db_conn.cursor.execute(f'PRAGMA table_info("{table_name}")')
        return {row[1] for row in db_conn.cursor.fetchall()}

    @staticmethod
    def migrate_legacy_to_v2(
        db_conn,
        legacy_crypto,
        crypto,
        password,
        cancel_check=None,
        progress_callback=None,
    ):
        AuthService._raise_if_cancelled(cancel_check)
        db_conn.conn.execute("PRAGMA secure_delete=ON;")
        if getattr(db_conn, "db_path", ":memory:") != ":memory:":
            db_conn.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            AuthService.create_pre_migration_backup(
                db_conn.db_path, cancel_check=cancel_check
            )

        AuthService._raise_if_cancelled(cancel_check)
        new_salt = os.urandom(16)
        data_key = CryptoManager.generate_data_key()
        new_crypto = CryptoManager()
        new_crypto.load_data_key(data_key)
        password_key = CryptoManager.derive_password_key(password, new_salt)
        AuthService._raise_if_cancelled(cancel_check)
        wrapped_data_key = CryptoManager.wrap_data_key(data_key, password_key)

        db_conn.cursor.execute("SELECT COUNT(*) FROM items")
        item_total = int(db_conn.cursor.fetchone()[0])
        db_conn.cursor.execute("SELECT COUNT(*) FROM media_chunks")
        chunk_total = int(db_conn.cursor.fetchone()[0])
        total = max(1, item_total + chunk_total)
        current = 0

        try:
            db_conn.conn.execute("BEGIN IMMEDIATE")

            db_conn.cursor.execute("SELECT id FROM items ORDER BY id")
            item_ids = [row[0] for row in db_conn.cursor.fetchall()]
            for item_id in item_ids:
                AuthService._raise_if_cancelled(cancel_check)
                db_conn.cursor.execute(
                    "SELECT title, text_content, thumbnail, full_data FROM items WHERE id=?",
                    (item_id,),
                )
                title, text_content, thumbnail, full_data = db_conn.cursor.fetchone()
                db_conn.cursor.execute(
                    "UPDATE items SET title=?, text_content=?, thumbnail=?, full_data=? WHERE id=?",
                    (
                        _reenc_blob(legacy_crypto, new_crypto, title),
                        _reenc_blob(legacy_crypto, new_crypto, text_content),
                        _reenc_blob(legacy_crypto, new_crypto, thumbnail),
                        _reenc_blob(legacy_crypto, new_crypto, full_data),
                        item_id,
                    ),
                )
                current += 1
                if progress_callback:
                    progress_callback(current, total, "Migrating encrypted items...")

            db_conn.cursor.execute("SELECT id FROM media_chunks ORDER BY item_id, chunk_index")
            chunk_ids = [row[0] for row in db_conn.cursor.fetchall()]
            for chunk_id in chunk_ids:
                AuthService._raise_if_cancelled(cancel_check)
                db_conn.cursor.execute("SELECT data FROM media_chunks WHERE id=?", (chunk_id,))
                data = db_conn.cursor.fetchone()[0]
                db_conn.cursor.execute(
                    "UPDATE media_chunks SET data=? WHERE id=?",
                    (_reenc_blob(legacy_crypto, new_crypto, data), chunk_id),
                )
                current += 1
                if progress_callback:
                    progress_callback(current, total, "Migrating media chunks...")

            AuthService._raise_if_cancelled(cancel_check)
            db_conn.set_metadata("auth_salt", new_salt, commit=False)
            db_conn.set_metadata("wrapped_data_key", wrapped_data_key, commit=False)
            db_conn.set_metadata(
                "auth_check",
                new_crypto.encrypt(AuthService.AUTH_CHECK_PLAINTEXT),
                commit=False,
            )
            db_conn.set_metadata("crypto_version", AuthService.CRYPTO_VERSION, commit=False)
            AuthService.write_kdf_metadata(db_conn, commit=False)
            db_conn.conn.commit()
        except OperationCancelledError:
            db_conn.conn.rollback()
            raise
        except Exception as exc:
            db_conn.conn.rollback()
            raise AuthError("Failed to migrate database encryption") from exc

        crypto.load_data_key(data_key)
        if getattr(db_conn, "db_path", ":memory:") != ":memory:":
            try:
                db_conn.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            except sqlite3.Error:
                # Migration is committed; a busy checkpoint must not invalidate it.
                pass

    @staticmethod
    def create_pre_migration_backup(db_path, cancel_check=None):
        path = Path(db_path).resolve()
        backup_dir = path.parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = backup_dir / f"{path.stem}_pre_v2_migration_{stamp}{path.suffix}"

        def on_progress(_status, _remaining, _total):
            AuthService._raise_if_cancelled(cancel_check)

        try:
            uri = f"{path.as_uri()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=5.0)) as source:
                with closing(sqlite3.connect(backup_path)) as target:
                    source.backup(
                        target, pages=256, progress=on_progress, sleep=0.05
                    )
            return str(backup_path)
        except Exception:
            for suffix in ("", "-wal", "-shm", "-journal"):
                try:
                    os.remove(f"{backup_path}{suffix}")
                except OSError:
                    pass
            raise

    @staticmethod
    def _raise_if_cancelled(cancel_check):
        if cancel_check and cancel_check():
            raise OperationCancelledError("Operation cancelled")


def _reenc_blob(old_crypto, new_crypto, blob):
    if blob is None:
        return None
    return new_crypto.encrypt(old_crypto.decrypt(blob))
