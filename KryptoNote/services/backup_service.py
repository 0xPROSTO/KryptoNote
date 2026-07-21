import datetime
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from ..core.exceptions import OperationCancelledError


class BackupService:
    """Creates consistent SQLite backups without blocking on the UI connection."""

    @staticmethod
    def create(db_conn, service, cancel_check=None, progress_callback=None):
        """Compatibility wrapper that flushes changes before taking a backup."""
        service.commit_changes()
        db_path = getattr(db_conn, "db_path", None)
        source = getattr(db_conn, "conn", None)
        if source is not None and not isinstance(source, sqlite3.Connection):
            return BackupService._create_from_connection(
                source, db_path, cancel_check, progress_callback
            )
        if db_path == ":memory:":
            return BackupService._create_from_connection(
                source, db_path, cancel_check, progress_callback
            )
        return BackupService.create_from_path(
            db_path, cancel_check=cancel_check, progress_callback=progress_callback
        )

    @staticmethod
    def create_from_path(db_path, cancel_check=None, progress_callback=None):
        """Back up a file database using a dedicated read-only connection."""
        backup_path = None
        try:
            if not db_path or db_path == ":memory:":
                raise ValueError("A file-backed database is required")
            backup_path = BackupService._make_backup_path(db_path)
            uri = f"{Path(db_path).resolve().as_uri()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=5.0)) as source:
                BackupService._run_backup(
                    source, backup_path, cancel_check, progress_callback
                )
            return True, f"Backup created successfully:\n{backup_path}"
        except OperationCancelledError:
            BackupService._cleanup_partial_backup(backup_path)
            return False, "Backup cancelled"
        except Exception as exc:
            BackupService._cleanup_partial_backup(backup_path)
            return False, f"Failed to create backup:\n{exc}"

    @staticmethod
    def _create_from_connection(
        source, db_path, cancel_check=None, progress_callback=None
    ):
        backup_path = None
        try:
            backup_path = BackupService._make_backup_path(db_path)
            BackupService._run_backup(
                source, backup_path, cancel_check, progress_callback
            )
            return True, f"Backup created successfully:\n{backup_path}"
        except OperationCancelledError:
            BackupService._cleanup_partial_backup(backup_path)
            return False, "Backup cancelled"
        except Exception as exc:
            BackupService._cleanup_partial_backup(backup_path)
            return False, f"Failed to create backup:\n{exc}"

    @staticmethod
    def _run_backup(source, backup_path, cancel_check, progress_callback):
        def on_progress(_status, remaining, total):
            if cancel_check and cancel_check():
                raise OperationCancelledError("Backup cancelled")
            if progress_callback:
                progress_callback(total - remaining, total, "Creating backup...")

        with closing(sqlite3.connect(backup_path)) as target:
            if isinstance(source, sqlite3.Connection):
                source.backup(
                    target,
                    pages=256,
                    progress=on_progress,
                    sleep=0.05,
                )
            else:
                source.backup(target)

    @staticmethod
    def _make_backup_path(db_path):
        path = Path(db_path).resolve()
        backup_dir = path.parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return str(backup_dir / f"{path.stem}_{timestamp}{path.suffix}")

    @staticmethod
    def _cleanup_partial_backup(backup_path):
        if not backup_path:
            return
        for suffix in ("", "-wal", "-shm", "-journal"):
            try:
                os.remove(backup_path + suffix)
            except FileNotFoundError:
                pass
            except OSError:
                pass
