import os
import datetime
import sqlite3


class BackupService:
    """Creates encrypted database backups.

    Extracted from ZeroXXWindow.create_backup to decouple
    backup logic from the main window.
    """

    @staticmethod
    def create(db_conn, service):
        """Create a timestamped backup of the database.

        Args:
            db_conn: DatabaseConnection instance.
            service: NodeService (used to commit pending changes).

        Returns:
            tuple: (success: bool, message: str)
        """
        db_path = db_conn.db_path
        name, ext = os.path.splitext(os.path.basename(db_path))
        backup_dir = os.path.join(os.path.dirname(db_path), "backup")
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{name}_{timestamp}{ext}")
        service.commit_changes()

        try:
            backup_conn = sqlite3.connect(backup_path)
            db_conn.conn.backup(backup_conn)
            backup_conn.close()
            return True, f"Backup created successfully:\n{backup_path}"
        except Exception as e:
            return False, f"Failed to create backup:\n{e}"
