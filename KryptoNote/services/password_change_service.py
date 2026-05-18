import os
import sqlite3
import time

from cryptography.exceptions import InvalidTag

from ..core.crypto import CryptoManager
from ..core.exceptions import AuthError
from .auth_service import AuthService


class PasswordChangeService:
    """Atomically rewrap the database data key with a new password."""

    @staticmethod
    def change_password(db_path, current_password, new_password,
                        on_progress=None, on_finished=None, on_waiting_lock=None):
        conn = None
        try:
            if on_progress:
                on_progress(0, 1, "Verifying current password...")

            conn = PasswordChangeService._open_connection(db_path, on_waiting_lock)
            conn.execute("PRAGMA secure_delete=ON;")
            cursor = conn.cursor()

            salt = PasswordChangeService._get_metadata(cursor, "auth_salt")
            wrapped_data_key = PasswordChangeService._get_metadata(cursor, "wrapped_data_key")
            auth_check = PasswordChangeService._get_metadata(cursor, "auth_check")
            if not salt or not wrapped_data_key or not auth_check:
                raise AuthError("Database is not using envelope encryption")

            old_password_key = CryptoManager.derive_password_key(current_password, salt)
            data_key = CryptoManager.unwrap_data_key(wrapped_data_key, old_password_key)

            crypto = CryptoManager()
            crypto.load_data_key(data_key)
            if crypto.decrypt(auth_check) != AuthService.AUTH_CHECK_PLAINTEXT:
                raise AuthError("Incorrect password")

            if on_progress:
                on_progress(1, 2, "Updating password key...")

            new_salt = os.urandom(16)
            new_password_key = CryptoManager.derive_password_key(new_password, new_salt)
            new_wrapped_data_key = CryptoManager.wrap_data_key(data_key, new_password_key)

            conn.execute("BEGIN IMMEDIATE")
            PasswordChangeService._set_metadata(cursor, "auth_salt", new_salt)
            PasswordChangeService._set_metadata(cursor, "wrapped_data_key", new_wrapped_data_key)
            conn.commit()
            if db_path != ":memory:":
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

            if on_progress:
                on_progress(2, 2, "Password changed.")
            if on_finished:
                on_finished(True, "Password changed successfully")
        except InvalidTag:
            if conn:
                conn.rollback()
            if on_finished:
                on_finished(False, "Incorrect password")
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            if on_finished:
                on_finished(False, f"Password change failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    @staticmethod
    def _open_connection(db_path, on_waiting_lock):
        last_error = None
        for attempt in range(1, 9):
            try:
                c = sqlite3.connect(db_path, timeout=2.0)
                c.execute("PRAGMA busy_timeout=2000;")
                c.execute("PRAGMA journal_mode=WAL;")
                return c
            except sqlite3.OperationalError as e:
                last_error = e
                if "locked" not in str(e).lower() and "busy" not in str(e).lower():
                    raise
                if on_waiting_lock:
                    on_waiting_lock(attempt)
                time.sleep(min(0.25 * attempt, 1.5))
        raise last_error

    @staticmethod
    def _get_metadata(cursor, key):
        cursor.execute("SELECT value FROM metadata WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    @staticmethod
    def _set_metadata(cursor, key, value):
        cursor.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
