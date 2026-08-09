import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag

from ..core.crypto import CryptoManager
from ..core.database import DatabaseConnection, NodeRepository
from ..core.exceptions import (
    AuthError,
    CryptoError,
    OperationCancelledError,
    UnverifiableLegacyPassword,
)


class AuthService:
    """Handles project authentication and encryption migration."""

    AUTH_CHECK_PLAINTEXT = b"KryptoNote_Auth_OK"
    CRYPTO_VERSION = "3"
    _MIGRATION_ID_BATCH_SIZE = 256

    @staticmethod
    def authenticate(db_path, password_provider, mode):
        from .node_service import NodeService

        if mode not in {"create", "open"}:
            raise ValueError(f"Unsupported authentication mode: {mode}")

        crypto = CryptoManager()
        db_name = os.path.basename(db_path)
        db_conn = None
        if mode == "open":
            try:
                salt = DatabaseConnection.read_metadata_readonly(
                    db_path, "auth_salt"
                )
            except Exception as exc:
                raise AuthError(
                    "Corrupted database: unreadable metadata"
                ) from exc
            if not salt:
                raise AuthError(
                    "Corrupted database: missing authentication salt"
                )
            db_conn = DatabaseConnection(
                db_path,
                initialize=False,
                must_exist=True,
                writable=False,
            )
        else:
            password = AuthService._request_new_password(
                db_name, password_provider
            )
            db_conn = DatabaseConnection(db_path)
        try:
            if mode == "create":
                AuthService.initialize_v3_project(
                    db_conn, crypto, password
                )
            else:
                AuthService.verify_existing_password(
                    db_conn, crypto, salt, db_name, password_provider
                )

            db_conn.recover_interrupted_operations()

            repo = NodeRepository(db_conn, crypto)
            return db_conn, crypto, repo, NodeService(repo)
        except Exception:
            try:
                db_conn.close()
            except Exception:
                pass
            raise

    @staticmethod
    def create_new_password(db_conn, crypto, db_name, provider):
        password = AuthService._request_new_password(db_name, provider)
        AuthService.initialize_v3_project(db_conn, crypto, password)
        return db_conn.get_salt()

    @staticmethod
    def _request_new_password(db_name, provider):
        error_msg = None
        while True:
            pwd1, ok1 = provider("create", db_name, error_msg)
            if not ok1 or not pwd1:
                raise AuthError("Password entry cancelled")
            pwd2, ok2 = provider("confirm", db_name, None)
            if not ok2:
                raise AuthError("Password entry cancelled")
            if pwd1 == pwd2:
                return pwd1
            error_msg = "Passwords do not match"

    @staticmethod
    def verify_existing_password(db_conn, crypto, salt, db_name, provider):
        error_msg = None
        while True:
            pwd, ok = provider("enter", db_name, error_msg)
            if not ok or not pwd:
                raise AuthError("Password entry cancelled")
            try:
                AuthService.unlock_existing_database(
                    db_conn, crypto, pwd, salt
                )
                return
            except UnverifiableLegacyPassword:
                confirmation, confirmed = provider(
                    "confirm_legacy",
                    db_name,
                    "This empty legacy project cannot verify its password. "
                    "Enter the same password again to migrate it.",
                )
                if confirmed and confirmation == pwd:
                    AuthService.unlock_existing_database(
                        db_conn,
                        crypto,
                        pwd,
                        salt,
                        allow_unverifiable_legacy=True,
                    )
                    return
                error_msg = "Passwords do not match"
            except InvalidTag:
                error_msg = "Incorrect password"

    @staticmethod
    def unlock_existing_database(
        db_conn,
        crypto,
        password,
        salt,
        before_legacy_migration=None,
        cancel_check=None,
        progress_callback=None,
        allow_unverifiable_legacy=False,
    ):
        version = AuthService.crypto_version(db_conn)
        last_error = None
        verified_salt = None
        legacy_crypto = None
        for candidate_salt in AuthService.salt_candidates(salt):
            try:
                if version == 3:
                    AuthService._unlock_envelope_database(
                        db_conn,
                        crypto,
                        password,
                        candidate_salt,
                        cancel_check,
                    )
                    AuthService._verify_auth_check(crypto, db_conn, version=3)
                elif version == 2:
                    AuthService.unlock_v2_database(
                        db_conn,
                        crypto,
                        password,
                        candidate_salt,
                        cancel_check,
                    )
                    AuthService._verify_auth_check(crypto, db_conn, version=2)
                else:
                    legacy_crypto = AuthService._verify_legacy_password(
                        db_conn,
                        password,
                        candidate_salt,
                        cancel_check=cancel_check,
                        allow_unverifiable=allow_unverifiable_legacy,
                    )
                verified_salt = candidate_salt
                break
            except UnverifiableLegacyPassword:
                raise
            except (InvalidTag, CryptoError, TypeError, ValueError) as exc:
                last_error = exc
        if verified_salt is None:
            raise InvalidTag() from last_error

        # Credentials are proven while the connection is read-only. Only now
        # is the database reopened for schema/encryption migrations.
        if hasattr(db_conn, "promote_to_writable"):
            db_conn.promote_to_writable()
        current_version = AuthService.crypto_version(db_conn)
        if current_version != version:
            raise AuthError("Database changed while it was being unlocked")
        if version in {2, 3}:
            AuthService._unlock_envelope_database(
                db_conn,
                crypto,
                password,
                verified_salt,
                cancel_check,
            )
            AuthService._verify_auth_check(
                crypto, db_conn, version=version
            )
        else:
            legacy_crypto = AuthService._verify_legacy_password(
                db_conn,
                password,
                verified_salt,
                cancel_check=cancel_check,
                allow_unverifiable=allow_unverifiable_legacy,
            )

        backup_created = False

        def ensure_migration_backup():
            nonlocal backup_created
            if backup_created:
                return
            if before_legacy_migration:
                before_legacy_migration()
            db_path = getattr(db_conn, "db_path", ":memory:")
            if db_path != ":memory:":
                AuthService.create_pre_migration_backup(
                    db_path, cancel_check=cancel_check
                )
            backup_created = True

        db_conn.initialize_schema(
            before_destructive_migration=ensure_migration_backup
        )

        if version == 2:
            ensure_migration_backup()
            AuthService.migrate_v2_to_v3(
                db_conn,
                crypto,
                cancel_check=cancel_check,
                progress_callback=progress_callback,
                backup_already_created=backup_created,
            )
        elif version == 1:
            ensure_migration_backup()
            AuthService.migrate_legacy_to_v3(
                db_conn,
                legacy_crypto,
                crypto,
                password,
                cancel_check=cancel_check,
                progress_callback=progress_callback,
                backup_already_created=backup_created,
            )
        AuthService._verify_auth_check(crypto, db_conn, version=3)

    @staticmethod
    def crypto_version(db_conn):
        try:
            version = int(db_conn.get_crypto_version())
        except Exception as exc:
            raise AuthError("Invalid encryption version metadata") from exc
        if version == 1 and db_conn.get_wrapped_data_key() is not None:
            version = 2
        if version not in {1, 2, 3}:
            raise AuthError(f"Unsupported encryption version: {version}")
        return version

    @staticmethod
    def is_v2_database(db_conn):
        return AuthService.crypto_version(db_conn) == 2

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
    def write_kdf_metadata(db_conn, commit=False):
        db_conn.set_metadata(
            "kdf_name", CryptoManager.KDF_NAME, commit=False
        )
        db_conn.set_metadata(
            "kdf_iterations",
            str(CryptoManager.KDF_ITERATIONS),
            commit=False,
        )
        db_conn.set_metadata(
            "kdf_memory_cost",
            str(CryptoManager.KDF_MEMORY_COST),
            commit=False,
        )
        db_conn.set_metadata(
            "kdf_lanes", str(CryptoManager.KDF_LANES), commit=False
        )
        if commit:
            db_conn.conn.commit()

    @staticmethod
    def read_kdf_params(db_conn):
        return AuthService.read_kdf_params_from_getter(
            db_conn.get_metadata
        )

    @staticmethod
    def read_kdf_params_from_getter(get_metadata):
        name = (
            AuthService._metadata_text(get_metadata("kdf_name"))
            or CryptoManager.KDF_NAME
        )
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
                raise AuthError(
                    "Invalid KDF metadata encoding"
                ) from exc
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
    def initialize_v3_project(
        db_conn, crypto, password, cancel_check=None
    ):
        AuthService._raise_if_cancelled(cancel_check)
        salt = os.urandom(16)
        data_key = CryptoManager.generate_data_key()
        password_key = CryptoManager.derive_password_key(password, salt)
        AuthService._raise_if_cancelled(cancel_check)
        wrapped_data_key = CryptoManager.wrap_data_key(
            data_key, password_key
        )
        crypto.load_data_key(data_key)
        db_conn.set_metadata("auth_salt", salt, commit=False)
        db_conn.set_metadata(
            "wrapped_data_key", wrapped_data_key, commit=False
        )
        db_conn.set_metadata(
            "auth_check",
            crypto.encrypt(
                AuthService.AUTH_CHECK_PLAINTEXT,
                aad=crypto.auth_check_aad(),
            ),
            commit=False,
        )
        db_conn.set_metadata(
            "crypto_version", AuthService.CRYPTO_VERSION, commit=False
        )
        AuthService.write_kdf_metadata(db_conn, commit=False)
        db_conn.conn.commit()

    # Compatibility name retained for integrations built against 3.2.x.
    initialize_v2_project = initialize_v3_project

    @staticmethod
    def _unlock_envelope_database(
        db_conn, crypto, password, salt, cancel_check=None
    ):
        wrapped_data_key = db_conn.get_wrapped_data_key()
        if not wrapped_data_key:
            raise AuthError(
                "Corrupted database: missing wrapped data key"
            )
        if not db_conn.get_auth_check():
            raise AuthError("Corrupted database: missing auth check")
        AuthService._raise_if_cancelled(cancel_check)
        password_key = CryptoManager.derive_password_key(
            password,
            salt,
            **AuthService.read_kdf_params(db_conn),
        )
        AuthService._raise_if_cancelled(cancel_check)
        crypto.load_data_key(
            CryptoManager.unwrap_data_key(
                wrapped_data_key, password_key
            )
        )

    @staticmethod
    def unlock_v2_database(
        db_conn, crypto, password, salt, cancel_check=None
    ):
        AuthService._unlock_envelope_database(
            db_conn, crypto, password, salt, cancel_check
        )

    @staticmethod
    def _verify_auth_check(crypto, db_conn, version):
        auth_check = db_conn.get_auth_check()
        if not auth_check:
            raise AuthError("Corrupted database: missing auth check")
        if version == 3:
            plaintext = crypto.decrypt(
                auth_check, aad=crypto.auth_check_aad()
            )
        else:
            plaintext = crypto.decrypt_legacy(auth_check)
        if plaintext != AuthService.AUTH_CHECK_PLAINTEXT:
            raise InvalidTag()

    @staticmethod
    def unlock_and_migrate_legacy(
        db_conn,
        crypto,
        password,
        salt,
        before_migration=None,
        cancel_check=None,
        progress_callback=None,
        allow_unverifiable=False,
    ):
        legacy_crypto = AuthService._verify_legacy_password(
            db_conn,
            password,
            salt,
            cancel_check=cancel_check,
            allow_unverifiable=allow_unverifiable,
        )
        if before_migration:
            before_migration()
        AuthService.migrate_legacy_to_v3(
            db_conn,
            legacy_crypto,
            crypto,
            password,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
        )

    @staticmethod
    def _verify_legacy_password(
        db_conn,
        password,
        salt,
        cancel_check=None,
        allow_unverifiable=False,
    ):
        AuthService._raise_if_cancelled(cancel_check)
        legacy_crypto = CryptoManager()
        legacy_crypto.derive_key(password, salt)
        AuthService._raise_if_cancelled(cancel_check)
        auth_check = db_conn.get_auth_check()
        if auth_check:
            if (
                legacy_crypto.decrypt_legacy(auth_check)
                != AuthService.AUTH_CHECK_PLAINTEXT
            ):
                raise InvalidTag()
        else:
            AuthService._verify_legacy_payload_decryptable(
                db_conn,
                legacy_crypto,
                allow_unverifiable=allow_unverifiable,
            )
        return legacy_crypto

    @staticmethod
    def _verify_legacy_payload_decryptable(
        db_conn, legacy_crypto, allow_unverifiable=False
    ):
        found_blob = False
        last_error = None
        for blob in AuthService._iter_legacy_probe_blobs(db_conn):
            found_blob = True
            try:
                legacy_crypto.decrypt_legacy(blob)
                return
            except (InvalidTag, CryptoError, TypeError, ValueError) as exc:
                last_error = exc
        if found_blob:
            raise InvalidTag() from last_error
        if not allow_unverifiable:
            raise UnverifiableLegacyPassword(
                "Empty legacy project has no authentication check"
            )

    @staticmethod
    def _iter_legacy_probe_blobs(db_conn):
        item_columns = AuthService._table_columns(db_conn, "items")
        for column in (
            "title",
            "text_content",
            "thumbnail",
            "full_data",
            "original_filename",
        ):
            if column not in item_columns:
                continue
            db_conn.cursor.execute(
                f'SELECT "{column}" FROM items '
                f'WHERE "{column}" IS NOT NULL ORDER BY id LIMIT 3'
            )
            for (blob,) in db_conn.cursor.fetchall():
                if blob:
                    yield blob
        if "data" in AuthService._table_columns(
            db_conn, "media_chunks"
        ):
            db_conn.cursor.execute(
                'SELECT "data" FROM media_chunks '
                'WHERE "data" IS NOT NULL ORDER BY id LIMIT 3'
            )
            for (blob,) in db_conn.cursor.fetchall():
                if blob:
                    yield blob
        if "name" in AuthService._table_columns(db_conn, "tags"):
            db_conn.cursor.execute(
                'SELECT "name" FROM tags '
                'WHERE "name" IS NOT NULL ORDER BY id LIMIT 3'
            )
            for (blob,) in db_conn.cursor.fetchall():
                if blob:
                    yield blob

    @staticmethod
    def _table_columns(db_conn, table_name):
        db_conn.cursor.execute(f'PRAGMA table_info("{table_name}")')
        return {row[1] for row in db_conn.cursor.fetchall()}

    @staticmethod
    def migrate_v2_to_v3(
        db_conn,
        crypto,
        cancel_check=None,
        progress_callback=None,
        backup_already_created=False,
    ):
        AuthService._migrate_payloads_to_v3(
            db_conn,
            crypto,
            crypto,
            password=None,
            replace_envelope=False,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            backup_already_created=backup_already_created,
        )

    @staticmethod
    def migrate_legacy_to_v3(
        db_conn,
        legacy_crypto,
        crypto,
        password,
        cancel_check=None,
        progress_callback=None,
        backup_already_created=False,
    ):
        AuthService._migrate_payloads_to_v3(
            db_conn,
            legacy_crypto,
            crypto,
            password=password,
            replace_envelope=True,
            cancel_check=cancel_check,
            progress_callback=progress_callback,
            backup_already_created=backup_already_created,
        )

    # Compatibility name retained for integrations built against 3.2.x.
    migrate_legacy_to_v2 = migrate_legacy_to_v3

    @staticmethod
    def _iter_migration_ids(conn, table_name):
        if table_name not in {"items", "media_chunks", "tags"}:
            raise ValueError("Unsupported migration table")

        last_id = None
        while True:
            if last_id is None:
                rows = conn.execute(
                    f"SELECT id FROM {table_name} "
                    "ORDER BY id LIMIT ?",
                    (AuthService._MIGRATION_ID_BATCH_SIZE,),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT id FROM {table_name} "
                    "WHERE id > ? ORDER BY id LIMIT ?",
                    (
                        last_id,
                        AuthService._MIGRATION_ID_BATCH_SIZE,
                    ),
                ).fetchall()
            if not rows:
                return
            for row_id, in rows:
                yield row_id
            last_id = rows[-1][0]

    @staticmethod
    def _migrate_payloads_to_v3(
        db_conn,
        old_crypto,
        output_crypto,
        password,
        replace_envelope,
        cancel_check=None,
        progress_callback=None,
        backup_already_created=False,
    ):
        AuthService._raise_if_cancelled(cancel_check)
        db_conn.conn.execute("PRAGMA secure_delete=ON;")
        db_path = getattr(db_conn, "db_path", ":memory:")
        if db_path != ":memory:" and not backup_already_created:
            db_conn.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            AuthService.create_pre_migration_backup(
                db_path, cancel_check=cancel_check
            )
        AuthService._raise_if_cancelled(cancel_check)

        if replace_envelope:
            new_salt = os.urandom(16)
            data_key = CryptoManager.generate_data_key()
            new_crypto = CryptoManager()
            new_crypto.load_data_key(data_key)
            AuthService._raise_if_cancelled(cancel_check)
            password_key = CryptoManager.derive_password_key(
                password, new_salt
            )
            AuthService._raise_if_cancelled(cancel_check)
            wrapped_data_key = CryptoManager.wrap_data_key(
                data_key, password_key
            )
        else:
            new_salt = None
            data_key = output_crypto.key
            new_crypto = output_crypto
            wrapped_data_key = None

        item_count = int(
            db_conn.conn.execute(
                "SELECT COUNT(*) FROM items"
            ).fetchone()[0]
        )
        chunk_count = int(
            db_conn.conn.execute(
                "SELECT COUNT(*) FROM media_chunks"
            ).fetchone()[0]
        )
        tag_count = int(
            db_conn.conn.execute(
                "SELECT COUNT(*) FROM tags"
            ).fetchone()[0]
        )
        total = max(1, item_count + chunk_count + tag_count)
        current = 0
        try:
            AuthService._raise_if_cancelled(cancel_check)
            db_conn.conn.execute("BEGIN IMMEDIATE")
            fields = (
                "title",
                "text_content",
                "thumbnail",
                "full_data",
                "original_filename",
            )
            for item_id in AuthService._iter_migration_ids(
                db_conn.conn, "items"
            ):
                AuthService._raise_if_cancelled(cancel_check)
                row = db_conn.conn.execute(
                    "SELECT title, text_content, thumbnail, full_data, "
                    "original_filename FROM items WHERE id=?",
                    (item_id,),
                ).fetchone()
                if row is None:
                    raise sqlite3.DatabaseError(
                        "Item disappeared during migration"
                    )
                values = [
                    _reenc_blob(
                        old_crypto,
                        new_crypto,
                        blob,
                        new_crypto.item_aad(item_id, field),
                    )
                    for field, blob in zip(fields, row)
                ]
                db_conn.conn.execute(
                    "UPDATE items SET title=?, text_content=?, thumbnail=?, "
                    "full_data=?, original_filename=? WHERE id=?",
                    (*values, item_id),
                )
                current += 1
                if progress_callback:
                    progress_callback(
                        current, total, "Migrating encrypted items..."
                    )

            for chunk_id in AuthService._iter_migration_ids(
                db_conn.conn, "media_chunks"
            ):
                AuthService._raise_if_cancelled(cancel_check)
                row = db_conn.conn.execute(
                    "SELECT item_id, chunk_index, data "
                    "FROM media_chunks WHERE id=?",
                    (chunk_id,),
                ).fetchone()
                if row is None:
                    raise sqlite3.DatabaseError(
                        "Media chunk disappeared during migration"
                    )
                item_id, chunk_index, blob = row
                db_conn.conn.execute(
                    "UPDATE media_chunks SET data=? WHERE id=?",
                    (
                        _reenc_blob(
                            old_crypto,
                            new_crypto,
                            blob,
                            new_crypto.chunk_aad(item_id, chunk_index),
                        ),
                        chunk_id,
                    ),
                )
                current += 1
                if progress_callback:
                    progress_callback(
                        current, total, "Migrating media chunks..."
                    )

            for tag_id in AuthService._iter_migration_ids(
                db_conn.conn, "tags"
            ):
                AuthService._raise_if_cancelled(cancel_check)
                row = db_conn.conn.execute(
                    "SELECT name FROM tags WHERE id=?",
                    (tag_id,),
                ).fetchone()
                if row is None:
                    raise sqlite3.DatabaseError(
                        "Tag disappeared during migration"
                    )
                blob = row[0]
                db_conn.conn.execute(
                    "UPDATE tags SET name=? WHERE id=?",
                    (
                        _reenc_blob(
                            old_crypto,
                            new_crypto,
                            blob,
                            new_crypto.tag_aad(tag_id),
                        ),
                        tag_id,
                    ),
                )
                current += 1
                if progress_callback:
                    progress_callback(
                        current, total, "Migrating encrypted tags..."
                    )

            AuthService._raise_if_cancelled(cancel_check)
            if replace_envelope:
                db_conn.set_metadata(
                    "auth_salt", new_salt, commit=False
                )
                db_conn.set_metadata(
                    "wrapped_data_key",
                    wrapped_data_key,
                    commit=False,
                )
                AuthService.write_kdf_metadata(
                    db_conn, commit=False
                )
            db_conn.set_metadata(
                "auth_check",
                new_crypto.encrypt(
                    AuthService.AUTH_CHECK_PLAINTEXT,
                    aad=new_crypto.auth_check_aad(),
                ),
                commit=False,
            )
            db_conn.set_metadata(
                "crypto_version",
                AuthService.CRYPTO_VERSION,
                commit=False,
            )
            db_conn.conn.commit()
        except OperationCancelledError:
            db_conn.conn.rollback()
            raise
        except Exception as exc:
            db_conn.conn.rollback()
            raise AuthError(
                "Failed to migrate database encryption"
            ) from exc

        output_crypto.load_data_key(data_key)
        if db_path != ":memory:":
            try:
                db_conn.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            except sqlite3.Error:
                pass

    @staticmethod
    def create_pre_migration_backup(db_path, cancel_check=None):
        path = Path(db_path).resolve()
        backup_dir = path.parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = (
            backup_dir
            / f"{path.stem}_pre_v3_migration_{stamp}{path.suffix}"
        )

        def on_progress(_status, _remaining, _total):
            AuthService._raise_if_cancelled(cancel_check)

        try:
            uri = f"{path.as_uri()}?mode=ro"
            with closing(
                sqlite3.connect(uri, uri=True, timeout=5.0)
            ) as source:
                with closing(sqlite3.connect(backup_path)) as target:
                    source.backup(
                        target,
                        pages=256,
                        progress=on_progress,
                        sleep=0.05,
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


def _reenc_blob(old_crypto, new_crypto, blob, aad):
    if blob is None:
        return None
    return new_crypto.encrypt(
        old_crypto.decrypt_legacy(blob),
        aad=aad,
    )
