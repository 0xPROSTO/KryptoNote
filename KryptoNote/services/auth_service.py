import os
import shutil
from datetime import datetime

from cryptography.exceptions import InvalidTag

from ..core.crypto import CryptoManager
from ..core.database import DatabaseConnection, NodeRepository
from ..core.exceptions import AuthError, CryptoError


class AuthService:
    """Handles project authentication and encryption migration."""

    AUTH_CHECK_PLAINTEXT = b"KryptoNote_Auth_OK"
    CRYPTO_VERSION = "2"

    @staticmethod
    def authenticate(db_path, password_provider):
        from .node_service import NodeService

        db_conn = DatabaseConnection(db_path)
        try:
            crypto = CryptoManager()
            salt = db_conn.get_salt()
            db_name = os.path.basename(db_path)

            if not salt:
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
                db_conn.conn.close()
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
    ):
        last_error = None
        is_v2 = AuthService.is_v2_database(db_conn)

        for candidate_salt in AuthService.salt_candidates(salt):
            try:
                if is_v2:
                    AuthService.unlock_v2_database(
                        db_conn, crypto, password, candidate_salt
                    )
                else:
                    AuthService.unlock_and_migrate_legacy(
                        db_conn,
                        crypto,
                        password,
                        candidate_salt,
                        before_migration=before_legacy_migration,
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
    def initialize_v2_project(db_conn, crypto, password):
        salt = os.urandom(16)
        data_key = CryptoManager.generate_data_key()
        password_key = CryptoManager.derive_password_key(password, salt)
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
        db_conn.set_metadata("kdf_name", CryptoManager.KDF_NAME, commit=False)
        db_conn.set_metadata("kdf_iterations", str(CryptoManager.KDF_ITERATIONS), commit=False)
        db_conn.set_metadata("kdf_memory_cost", str(CryptoManager.KDF_MEMORY_COST), commit=False)
        db_conn.set_metadata("kdf_lanes", str(CryptoManager.KDF_LANES), commit=False)
        db_conn.conn.commit()

    @staticmethod
    def unlock_v2_database(db_conn, crypto, password, salt):
        wrapped_data_key = db_conn.get_wrapped_data_key()
        auth_check = db_conn.get_auth_check()
        if not wrapped_data_key:
            raise AuthError("Corrupted database: missing wrapped data key")
        if not auth_check:
            raise AuthError("Corrupted database: missing auth check")

        password_key = CryptoManager.derive_password_key(password, salt)
        data_key = CryptoManager.unwrap_data_key(wrapped_data_key, password_key)
        crypto.load_data_key(data_key)

    @staticmethod
    def unlock_and_migrate_legacy(
        db_conn,
        crypto,
        password,
        salt,
        before_migration=None,
    ):
        legacy_crypto = CryptoManager()
        legacy_crypto.derive_key(password, salt)

        auth_check = db_conn.get_auth_check()
        if auth_check:
            if legacy_crypto.decrypt(auth_check) != AuthService.AUTH_CHECK_PLAINTEXT:
                raise InvalidTag()
        else:
            AuthService._verify_legacy_payload_decryptable(db_conn, legacy_crypto)

        if before_migration:
            before_migration()

        AuthService.migrate_legacy_to_v2(db_conn, legacy_crypto, crypto, password)

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
    def migrate_legacy_to_v2(db_conn, legacy_crypto, crypto, password):
        db_conn.conn.execute("PRAGMA secure_delete=ON;")
        if getattr(db_conn, "db_path", ":memory:") != ":memory:":
            db_conn.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            AuthService.create_pre_migration_backup(db_conn.db_path)

        new_salt = os.urandom(16)
        data_key = CryptoManager.generate_data_key()
        new_crypto = CryptoManager()
        new_crypto.load_data_key(data_key)
        password_key = CryptoManager.derive_password_key(password, new_salt)
        wrapped_data_key = CryptoManager.wrap_data_key(data_key, password_key)

        try:
            db_conn.conn.execute("BEGIN IMMEDIATE")

            db_conn.cursor.execute("SELECT id FROM items ORDER BY id")
            item_ids = [row[0] for row in db_conn.cursor.fetchall()]
            for item_id in item_ids:
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

            db_conn.cursor.execute("SELECT id FROM media_chunks ORDER BY item_id, chunk_index")
            chunk_ids = [row[0] for row in db_conn.cursor.fetchall()]
            for chunk_id in chunk_ids:
                db_conn.cursor.execute("SELECT data FROM media_chunks WHERE id=?", (chunk_id,))
                data = db_conn.cursor.fetchone()[0]
                db_conn.cursor.execute(
                    "UPDATE media_chunks SET data=? WHERE id=?",
                    (_reenc_blob(legacy_crypto, new_crypto, data), chunk_id),
                )

            db_conn.set_metadata("auth_salt", new_salt, commit=False)
            db_conn.set_metadata("wrapped_data_key", wrapped_data_key, commit=False)
            db_conn.set_metadata(
                "auth_check",
                new_crypto.encrypt(AuthService.AUTH_CHECK_PLAINTEXT),
                commit=False,
            )
            db_conn.set_metadata("crypto_version", AuthService.CRYPTO_VERSION, commit=False)
            db_conn.set_metadata("kdf_name", CryptoManager.KDF_NAME, commit=False)
            db_conn.set_metadata("kdf_iterations", str(CryptoManager.KDF_ITERATIONS), commit=False)
            db_conn.set_metadata("kdf_memory_cost", str(CryptoManager.KDF_MEMORY_COST), commit=False)
            db_conn.set_metadata("kdf_lanes", str(CryptoManager.KDF_LANES), commit=False)
            db_conn.conn.commit()
        except Exception as exc:
            db_conn.conn.rollback()
            raise AuthError("Failed to migrate database encryption") from exc

        crypto.load_data_key(data_key)
        if getattr(db_conn, "db_path", ":memory:") != ":memory:":
            db_conn.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

    @staticmethod
    def create_pre_migration_backup(db_path):
        backup_dir = os.path.join(os.path.dirname(db_path), "backup")
        os.makedirs(backup_dir, exist_ok=True)
        name, ext = os.path.splitext(os.path.basename(db_path))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{name}_pre_v2_migration_{stamp}{ext}")
        shutil.copy2(db_path, backup_path)
        for suffix in ("-wal", "-shm"):
            sidecar = db_path + suffix
            if os.path.exists(sidecar):
                shutil.copy2(sidecar, backup_path + suffix)
        return backup_path


def _reenc_blob(old_crypto, new_crypto, blob):
    if blob is None:
        return None
    return new_crypto.encrypt(old_crypto.decrypt(blob))
