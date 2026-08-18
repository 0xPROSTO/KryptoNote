import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = 3
STAGED_STORAGE_STATE = "importing"
READY_STORAGE_STATE = "ready"
RECOVERY_METADATA_KEY = "db_maintenance_state"
STAGED_CLEANUP_BATCH_SIZE = 128
OPERATION_LOCK_SUFFIX = ".operations.lock"


class DatabaseOperationLock:
    """Cross-process lock for operations that publish staged database rows."""

    def __init__(self, db_path):
        self._db_path = db_path
        self._handle = None
        self._acquired = False

    @property
    def lock_path(self):
        if not self._db_path or self._db_path == ":memory:":
            return None
        path = Path(self._db_path).resolve()
        return Path(f"{path}{OPERATION_LOCK_SUFFIX}")

    def acquire(self):
        if self._acquired:
            return True
        lock_path = self.lock_path
        if lock_path is None:
            self._acquired = True
            return True

        handle = open(lock_path, "a+b", buffering=0)
        try:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(
                    handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
        except OSError:
            handle.close()
            return False
        except Exception:
            handle.close()
            raise

        self._handle = handle
        self._acquired = True
        return True

    def release(self):
        if not self._acquired:
            return
        handle, self._handle = self._handle, None
        self._acquired = False
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            handle.close()

    def __enter__(self):
        if not self.acquire():
            raise sqlite3.OperationalError(
                "Another media import or graph copy is already active"
            )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False


def try_acquire_database_operation_lock(db_path):
    operation_lock = DatabaseOperationLock(db_path)
    return operation_lock if operation_lock.acquire() else None


def acquire_database_operation_lock(db_path):
    operation_lock = try_acquire_database_operation_lock(db_path)
    if operation_lock is None:
        raise sqlite3.OperationalError(
            "Another media import or graph copy is already active"
        )
    return operation_lock


def configure_sqlite_connection(
    conn,
    *,
    writable=True,
    busy_timeout_ms=5000,
    enable_wal=True,
):
    """Apply the shared runtime policy to one SQLite connection."""
    conn.execute("PRAGMA foreign_keys=ON;")
    timeout_ms = max(0, int(busy_timeout_ms))
    conn.execute(f"PRAGMA busy_timeout={timeout_ms};")
    if writable and enable_wal:
        conn.execute("PRAGMA journal_mode=WAL;")
    if writable:
        conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn


def open_sqlite_connection(
    db_path,
    *,
    timeout=30.0,
    writable=True,
    must_exist=False,
    enable_wal=True,
):
    timeout = max(0.0, float(timeout))
    if writable and must_exist and db_path != ":memory:":
        path = Path(db_path).resolve()
        conn = sqlite3.connect(
            f"{path.as_uri()}?mode=rw", uri=True, timeout=timeout
        )
    elif writable:
        conn = sqlite3.connect(db_path, timeout=timeout)
    else:
        if db_path == ":memory:":
            raise ValueError("A read-only in-memory database is not supported")
        path = Path(db_path).resolve()
        conn = sqlite3.connect(
            f"{path.as_uri()}?mode=ro", uri=True, timeout=timeout
        )
    try:
        return configure_sqlite_connection(
            conn,
            writable=writable,
            busy_timeout_ms=round(timeout * 1000),
            enable_wal=enable_wal,
        )
    except Exception:
        conn.close()
        raise


def cleanup_staged_items(
    conn,
    item_ids=None,
    *,
    cancel_check=None,
    progress_callback=None,
    batch_size=STAGED_CLEANUP_BATCH_SIZE,
):
    """Delete hidden staged items in bounded, restart-safe transactions."""
    try:
        conn.rollback()
    except sqlite3.Error:
        pass

    if item_ids is None:
        selected_ids = [
            int(row[0])
            for row in conn.execute(
                "SELECT id FROM items WHERE storage_state=? ORDER BY id",
                (STAGED_STORAGE_STATE,),
            )
        ]
    else:
        requested = list(dict.fromkeys(int(item_id) for item_id in item_ids))
        selected_ids = []
        for start in range(0, len(requested), 900):
            batch = requested[start:start + 900]
            if not batch:
                continue
            placeholders = ",".join("?" for _ in batch)
            selected_ids.extend(
                int(row[0])
                for row in conn.execute(
                    "SELECT id FROM items WHERE storage_state=? "
                    f"AND id IN ({placeholders}) ORDER BY id",
                    (STAGED_STORAGE_STATE, *batch),
                )
            )

    if not selected_ids:
        return 0

    total_chunks = 0
    for start in range(0, len(selected_ids), 900):
        batch = selected_ids[start:start + 900]
        placeholders = ",".join("?" for _ in batch)
        total_chunks += int(
            conn.execute(
                "SELECT COUNT(*) FROM media_chunks "
                f"WHERE item_id IN ({placeholders})",
                batch,
            ).fetchone()[0]
            or 0
        )

    removed = 0
    batch_size = max(1, min(int(batch_size), 900))
    for start in range(0, len(selected_ids), 900):
        item_batch = selected_ids[start:start + 900]
        item_placeholders = ",".join("?" for _ in item_batch)
        while True:
            if cancel_check and cancel_check():
                from ..exceptions import OperationCancelledError

                raise OperationCancelledError("Database recovery cancelled")
            rows = conn.execute(
                "SELECT id FROM media_chunks "
                f"WHERE item_id IN ({item_placeholders}) "
                "ORDER BY id LIMIT ?",
                (*item_batch, batch_size),
            ).fetchall()
            if not rows:
                break
            chunk_ids = [int(row[0]) for row in rows]
            chunk_placeholders = ",".join("?" for _ in chunk_ids)
            conn.execute(
                "DELETE FROM media_chunks "
                f"WHERE id IN ({chunk_placeholders})",
                chunk_ids,
            )
            conn.commit()
            removed += len(chunk_ids)
            if progress_callback:
                progress_callback(
                    removed,
                    max(total_chunks, 1),
                    "Cleaning interrupted database operation...",
                )

    for start in range(0, len(selected_ids), 900):
        batch = selected_ids[start:start + 900]
        placeholders = ",".join("?" for _ in batch)
        conn.execute(
            "DELETE FROM items WHERE storage_state=? "
            f"AND id IN ({placeholders})",
            (STAGED_STORAGE_STATE, *batch),
        )
        conn.commit()
    return len(selected_ids)


def validate_database_integrity(conn, timings=None):
    """Validate SQLite pages, relations, and ready chunk sequences."""
    stage_started = time.perf_counter()
    try:
        check_rows = conn.execute("PRAGMA quick_check").fetchall()
    finally:
        if timings is not None:
            timings["quick_check"] = time.perf_counter() - stage_started
    if check_rows != [("ok",)]:
        raise sqlite3.DatabaseError(
            "Database check failed after interrupted maintenance"
        )

    stage_started = time.perf_counter()
    try:
        foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        if timings is not None:
            timings["foreign_key_check"] = time.perf_counter() - stage_started
    if foreign_key_errors:
        raise sqlite3.DatabaseError(
            "Interrupted operation left invalid database relations"
        )

    from ..constants import MEDIA_CHUNK_SIZE

    stage_started = time.perf_counter()
    try:
        invalid = conn.execute(
            """
            SELECT items.id
            FROM items
            LEFT JOIN media_chunks ON media_chunks.item_id = items.id
            WHERE items.storage_state=? AND items.is_chunked=1
            GROUP BY items.id
            HAVING COUNT(media_chunks.id) !=
                   CASE WHEN COALESCE(items.total_size, 0)=0 THEN 0
                        ELSE (items.total_size + ? - 1) / ? END
                OR (COUNT(media_chunks.id) > 0 AND
                    (MIN(media_chunks.chunk_index) != 0 OR
                     MAX(media_chunks.chunk_index) != COUNT(media_chunks.id)-1))
            LIMIT 1
            """,
            (READY_STORAGE_STATE, MEDIA_CHUNK_SIZE, MEDIA_CHUNK_SIZE),
        ).fetchone()
    finally:
        if timings is not None:
            timings["media_chunks"] = time.perf_counter() - stage_started
    if invalid:
        raise sqlite3.DatabaseError(
            f"Incomplete media data for item {invalid[0]}"
        )


class DatabaseConnection:
    @staticmethod
    def read_metadata_readonly(db_path, key):
        """Read metadata without creating or migrating the database file."""
        path = Path(db_path).resolve()
        uri = f"{path.as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            conn.execute("PRAGMA query_only=ON")
            row = conn.execute(
                "SELECT value FROM metadata WHERE key=?", (key,)
            ).fetchone()
        return row[0] if row else None

    def __init__(
        self,
        db_path,
        *,
        initialize=True,
        must_exist=False,
        writable=True,
        timeout=30.0,
        configure_wal=True,
    ):
        self.db_path = db_path
        self._timeout = max(0.0, float(timeout))
        self._must_exist = bool(must_exist)
        self._writable = bool(writable)
        self._wal_enabled = bool(writable and configure_wal and not initialize)
        self.conn = open_sqlite_connection(
            db_path,
            timeout=self._timeout,
            writable=self._writable,
            must_exist=self._must_exist,
            enable_wal=self._wal_enabled,
        )
        self._closed = False
        self._initialized = False
        self.cursor = self.conn.cursor()
        try:
            if initialize:
                self.initialize_schema()
        except Exception:
            self.conn.close()
            raise

    def promote_to_writable(self):
        """Reopen an authenticated read-only database without creating it."""
        if self._writable:
            return
        self.cursor.close()
        self.conn.close()
        self.conn = open_sqlite_connection(
            self.db_path,
            timeout=self._timeout,
            writable=True,
            must_exist=True,
            enable_wal=False,
        )
        self.cursor = self.conn.cursor()
        self._writable = True
        self._wal_enabled = False

    def get_schema_version(self):
        table = self.conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='metadata'"
        ).fetchone()
        if table is None:
            return 0
        row = self.conn.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        if row is None or row[0] in (None, "", b""):
            return 0
        value = row[0]
        if isinstance(value, bytes):
            try:
                value = value.decode("ascii")
            except UnicodeDecodeError as exc:
                raise sqlite3.DatabaseError(
                    "Invalid database schema version"
                ) from exc
        try:
            version = int(value)
        except (TypeError, ValueError) as exc:
            raise sqlite3.DatabaseError(
                "Invalid database schema version"
            ) from exc
        if version < 0:
            raise sqlite3.DatabaseError("Invalid database schema version")
        return version

    def initialize_schema(self, before_destructive_migration=None):
        """Validate and atomically migrate the database to this app's schema."""
        if self._initialized:
            return SCHEMA_VERSION
        if not self._writable:
            raise sqlite3.OperationalError(
                "Database must be authenticated and writable before migration"
            )

        current_version = self.get_schema_version()
        if current_version > SCHEMA_VERSION:
            raise sqlite3.DatabaseError(
                "Database schema is newer than this application supports: "
                f"{current_version} > {SCHEMA_VERSION}"
            )

        repair_counts = (
            self._legacy_repair_counts() if current_version < SCHEMA_VERSION else {}
        )
        if any(repair_counts.values()):
            if before_destructive_migration is None:
                details = ", ".join(
                    f"{name}={count}"
                    for name, count in repair_counts.items()
                    if count
                )
                raise sqlite3.DatabaseError(
                    "Legacy database repair requires a backup callback"
                    + (f" ({details})" if details else "")
                )
            before_destructive_migration()

        if not self._wal_enabled:
            configure_sqlite_connection(
                self.conn,
                writable=True,
                busy_timeout_ms=round(self._timeout * 1000),
                enable_wal=True,
            )
            self._wal_enabled = True

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self._apply_schema(current_version)
            foreign_key_errors = self.conn.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            if foreign_key_errors:
                raise sqlite3.DatabaseError(
                    "Database migration left invalid foreign-key relations"
                )
            if current_version < SCHEMA_VERSION:
                self.conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    ("schema_version", str(SCHEMA_VERSION)),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        self._initialized = True
        return SCHEMA_VERSION

    def _table_exists(self, table_name):
        return self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone() is not None

    def _table_columns(self, table_name):
        if not self._table_exists(table_name):
            return set()
        quoted_name = str(table_name).replace('"', '""')
        return {
            str(row[1])
            for row in self.conn.execute(
                f'PRAGMA table_info("{quoted_name}")'
            )
        }

    def _legacy_repair_counts(self):
        """Count rows that a legacy migration would have to discard."""
        counts = {}
        item_columns = self._table_columns("items")
        has_items = "id" in item_columns
        if has_items and "storage_state" in item_columns:
            counts["invalid_storage_states"] = int(
                self.conn.execute(
                    "SELECT COUNT(*) FROM items "
                    "WHERE storage_state IS NULL "
                    "OR storage_state NOT IN ('importing', 'ready')"
                ).fetchone()[0]
                or 0
            )

        connection_columns = self._table_columns("connections")
        if has_items and {"id", "start_id", "end_id"}.issubset(
            connection_columns
        ):
            counts["invalid_connections"] = int(
                self.conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM connections
                    WHERE start_id IS NULL OR end_id IS NULL
                       OR start_id NOT IN (SELECT id FROM items)
                       OR end_id NOT IN (SELECT id FROM items)
                    """
                ).fetchone()[0]
                or 0
            )
            counts["duplicate_connections"] = int(
                self.conn.execute(
                    """
                    SELECT COALESCE(SUM(pair_count - 1), 0)
                    FROM (
                        SELECT COUNT(*) AS pair_count
                        FROM connections
                        WHERE start_id IS NOT NULL AND end_id IS NOT NULL
                          AND start_id IN (SELECT id FROM items)
                          AND end_id IN (SELECT id FROM items)
                        GROUP BY min(start_id, end_id), max(start_id, end_id)
                        HAVING COUNT(*) > 1
                    )
                    """
                ).fetchone()[0]
                or 0
            )

        chunk_columns = self._table_columns("media_chunks")
        if has_items and {"id", "item_id", "chunk_index", "data"}.issubset(
            chunk_columns
        ):
            counts["invalid_media_chunks"] = int(
                self.conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM media_chunks
                    WHERE item_id IS NULL OR chunk_index IS NULL OR data IS NULL
                       OR item_id NOT IN (SELECT id FROM items)
                    """
                ).fetchone()[0]
                or 0
            )
            counts["duplicate_media_chunks"] = int(
                self.conn.execute(
                    """
                    SELECT COALESCE(SUM(chunk_count - 1), 0)
                    FROM (
                        SELECT COUNT(*) AS chunk_count
                        FROM media_chunks
                        WHERE item_id IS NOT NULL AND chunk_index IS NOT NULL
                          AND data IS NOT NULL
                          AND item_id IN (SELECT id FROM items)
                        GROUP BY item_id, chunk_index
                        HAVING COUNT(*) > 1
                    )
                    """
                ).fetchone()[0]
                or 0
            )

        item_tag_columns = self._table_columns("item_tags")
        tag_columns = self._table_columns("tags")
        if (
            has_items
            and "id" in tag_columns
            and {"item_id", "tag_id"}.issubset(item_tag_columns)
        ):
            counts["invalid_item_tags"] = int(
                self.conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM item_tags
                    WHERE item_id IS NULL OR tag_id IS NULL
                       OR item_id NOT IN (SELECT id FROM items)
                       OR tag_id NOT IN (SELECT id FROM tags)
                    """
                ).fetchone()[0]
                or 0
            )
        return counts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Close the SQLite connection. Safe to call more than once."""
        if self._closed:
            return
        self._closed = True
        try:
            self.cursor.close()
        finally:
            self.conn.close()

    def _apply_schema(self, from_version):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value BLOB)")

        self.cursor.execute("""
                            CREATE TABLE IF NOT EXISTS items
                            (
                                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                                type         TEXT,
                                title        BLOB,
                                x            REAL,
                                y            REAL,
                                width        REAL,
                                height       REAL,
                                text_content BLOB,
                                thumbnail    BLOB,
                                full_data    BLOB,
                                is_chunked   INTEGER DEFAULT 0,
                                total_size   INTEGER DEFAULT 0,
                                title_size   INTEGER DEFAULT 14,
                                text_size    INTEGER DEFAULT 10,
                                created_at   TEXT DEFAULT '',
                                updated_at   TEXT DEFAULT '',
                                media_width  INTEGER DEFAULT 0,
                                media_height INTEGER DEFAULT 0,
                                media_duration REAL DEFAULT 0,
                                 original_filename BLOB,
                                 media_metadata BLOB,
                                 storage_state TEXT NOT NULL DEFAULT 'ready',
                                 frame_locked INTEGER NOT NULL DEFAULT 0,
                                frame_color TEXT NOT NULL DEFAULT '',
                                frame_opacity REAL NOT NULL DEFAULT 0.21
                            )
                            """)

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS connections
            (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                start_id INTEGER NOT NULL,
                end_id   INTEGER NOT NULL,
                FOREIGN KEY (start_id) REFERENCES items (id) ON DELETE CASCADE,
                FOREIGN KEY (end_id) REFERENCES items (id) ON DELETE CASCADE
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS media_chunks
            (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id     INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                data        BLOB NOT NULL,
                UNIQUE (item_id, chunk_index),
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tags
            (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       BLOB NOT NULL,
                color      TEXT NOT NULL,
                created_at TEXT DEFAULT ''
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS item_tags
            (
                item_id INTEGER NOT NULL,
                tag_id  INTEGER NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (item_id, tag_id),
                FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
            )
            """
        )


        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks ON media_chunks(item_id, chunk_index)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_conn_start ON connections(start_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_conn_end ON connections(end_id)")
        self._migrate_db(from_version)
        self._migrate_tag_schema()
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_items_storage_state "
            "ON items(storage_state)"
        )
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_item_tags_tag ON item_tags(tag_id)")
        if from_version < SCHEMA_VERSION:
            self._migrate_relational_constraints()
        else:
            self._validate_current_relations()

    def _migrate_tag_schema(self):
        self.cursor.execute("PRAGMA table_info(item_tags)")
        columns = {column[1] for column in self.cursor.fetchall()}
        if "priority" not in columns:
            self.cursor.execute(
                "ALTER TABLE item_tags ADD COLUMN priority INTEGER NOT NULL DEFAULT 0"
            )
            # Initialise the new column exactly once. A zero priority is a valid
            # first position, so rewriting zeroes on every open corrupts order.
            self.cursor.execute(
                """
                UPDATE item_tags
                SET priority = (
                    SELECT COUNT(*)
                    FROM item_tags AS preceding
                    WHERE preceding.item_id = item_tags.item_id
                      AND preceding.tag_id < item_tags.tag_id
                )
                """
            )

    def _migrate_db(self, from_version):
        self.cursor.execute("PRAGMA table_info(items)")
        columns = [column[1] for column in self.cursor.fetchall()]
        if "title" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN title BLOB")
        if "is_chunked" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN is_chunked INTEGER DEFAULT 0")
        if "total_size" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN total_size INTEGER DEFAULT 0")
        if "title_size" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN title_size INTEGER DEFAULT 14")
        if "text_size" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN text_size INTEGER DEFAULT 10")
        if "created_at" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN created_at TEXT DEFAULT ''")
        if "updated_at" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN updated_at TEXT DEFAULT ''")
        if "media_width" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN media_width INTEGER DEFAULT 0")
        if "media_height" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN media_height INTEGER DEFAULT 0")
        if "media_duration" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN media_duration REAL DEFAULT 0")
        if "original_filename" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN original_filename BLOB")
        if "media_metadata" not in columns:
            self.cursor.execute("ALTER TABLE items ADD COLUMN media_metadata BLOB")
        if "storage_state" not in columns:
            self.cursor.execute(
                "ALTER TABLE items ADD COLUMN storage_state "
                "TEXT NOT NULL DEFAULT 'ready'"
            )
        invalid_storage_state = self.cursor.execute(
            "SELECT id FROM items WHERE storage_state IS NULL "
            "OR storage_state NOT IN ('importing', 'ready') LIMIT 1"
        ).fetchone()
        if invalid_storage_state and from_version >= SCHEMA_VERSION:
            raise sqlite3.DatabaseError(
                "Invalid storage_state in current database schema"
            )
        if invalid_storage_state:
            self.cursor.execute(
                "UPDATE items SET storage_state='ready' "
                "WHERE storage_state IS NULL "
                "OR storage_state NOT IN ('importing', 'ready')"
            )
        if "frame_locked" not in columns:
            self.cursor.execute(
                "ALTER TABLE items ADD COLUMN frame_locked "
                "INTEGER NOT NULL DEFAULT 0"
            )
        if "frame_color" not in columns:
            self.cursor.execute(
                "ALTER TABLE items ADD COLUMN frame_color "
                "TEXT NOT NULL DEFAULT ''"
            )
        if "frame_opacity" not in columns:
            self.cursor.execute(
                "ALTER TABLE items ADD COLUMN frame_opacity "
                "REAL NOT NULL DEFAULT 0.21"
            )

        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute("UPDATE items SET created_at=? WHERE created_at IS NULL OR created_at=''", (now,))
        self.cursor.execute("UPDATE items SET updated_at=created_at WHERE updated_at IS NULL OR updated_at=''")

    def recover_interrupted_operations(
        self, cancel_check=None, progress_callback=None
    ):
        """Remove staged rows, validate the database, then clear recovery state."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM items WHERE storage_state=?",
            (STAGED_STORAGE_STATE,),
        ).fetchone()
        pending_items = int(row[0] or 0)
        maintenance_state = self.get_metadata(RECOVERY_METADATA_KEY)
        if isinstance(maintenance_state, bytes):
            maintenance_state = maintenance_state.decode("utf-8", "replace")
        if not pending_items and not maintenance_state:
            return 0

        operation_lock = try_acquire_database_operation_lock(self.db_path)
        if operation_lock is None:
            # Another process is still publishing staged rows. They are live,
            # not interrupted, so leave them hidden and untouched.
            return 0

        try:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM items WHERE storage_state=?",
                (STAGED_STORAGE_STATE,),
            ).fetchone()
            pending_items = int(row[0] or 0)
            maintenance_state = self.get_metadata(RECOVERY_METADATA_KEY)
            if isinstance(maintenance_state, bytes):
                maintenance_state = maintenance_state.decode(
                    "utf-8", "replace"
                )
            if not pending_items and not maintenance_state:
                return 0

            if pending_items and not maintenance_state:
                self.set_metadata(
                    RECOVERY_METADATA_KEY,
                    "staged_cleanup",
                    commit=True,
                )

            cleanup_staged_items(
                self.conn,
                cancel_check=cancel_check,
                progress_callback=progress_callback,
            )

            validate_database_integrity(self.conn)

            self.conn.execute(
                "DELETE FROM metadata WHERE key=?",
                (RECOVERY_METADATA_KEY,),
            )
            self.conn.commit()

            return pending_items
        finally:
            operation_lock.release()

    def _migrate_relational_constraints(self):
        self.cursor.execute("DELETE FROM connections WHERE start_id IS NULL OR end_id IS NULL")
        self.cursor.execute(
            """
            DELETE FROM connections
            WHERE start_id NOT IN (SELECT id FROM items)
               OR end_id NOT IN (SELECT id FROM items)
            """
        )
        self.cursor.execute(
            """
            DELETE FROM media_chunks
            WHERE item_id IS NULL
               OR chunk_index IS NULL
               OR item_id NOT IN (SELECT id FROM items)
               OR data IS NULL
            """
        )
        self.cursor.execute(
            """
            DELETE FROM item_tags
            WHERE item_id IS NULL OR tag_id IS NULL
               OR item_id NOT IN (SELECT id FROM items)
               OR tag_id NOT IN (SELECT id FROM tags)
            """
        )
        self.cursor.execute(
            """
            DELETE FROM media_chunks
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM media_chunks
                GROUP BY item_id, chunk_index
            )
            """
        )
        if not self._table_has_cascade_foreign_keys(
            "connections", {"start_id", "end_id"}
        ):
            self._rebuild_connections_table()
        self.cursor.execute(
            """
            DELETE FROM connections
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM connections
                GROUP BY min(start_id, end_id), max(start_id, end_id)
            )
            """
        )
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_connections_pair "
            "ON connections(min(start_id, end_id), max(start_id, end_id))"
        )
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_media_chunks_item_index "
            "ON media_chunks(item_id, chunk_index)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks ON media_chunks(item_id, chunk_index)"
        )
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_conn_start ON connections(start_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_conn_end ON connections(end_id)")
        if self._table_has_cascade_foreign_keys("media_chunks", {"item_id"}):
            self.cursor.execute(
                "DROP TRIGGER IF EXISTS trg_items_delete_media_chunks"
            )
        else:
            # Rebuilding a legacy media_chunks table would copy every encrypted
            # multi-GB payload. Keep a trigger only for that legacy layout.
            self.cursor.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_items_delete_media_chunks
                AFTER DELETE ON items
                BEGIN
                    DELETE FROM media_chunks WHERE item_id = OLD.id;
                END
                """
            )

    def _validate_current_relations(self):
        repair_counts = self._legacy_repair_counts()
        if any(repair_counts.values()):
            details = ", ".join(
                f"{name}={count}"
                for name, count in repair_counts.items()
                if count
            )
            raise sqlite3.DatabaseError(
                "Current database schema contains invalid relations"
                + (f" ({details})" if details else "")
            )
        if not self._table_has_cascade_foreign_keys(
            "connections", {"start_id", "end_id"}
        ):
            raise sqlite3.DatabaseError(
                "Current database schema has unsupported connection keys"
            )
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_connections_pair "
            "ON connections(min(start_id, end_id), max(start_id, end_id))"
        )
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_media_chunks_item_index "
            "ON media_chunks(item_id, chunk_index)"
        )

    def _table_has_cascade_foreign_keys(self, table_name, expected_columns):
        self.cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
        rows = self.cursor.fetchall()
        cascade_columns = {
            row[3]
            for row in rows
            if row[2] == "items" and row[4] == "id" and row[6].upper() == "CASCADE"
        }
        return cascade_columns == set(expected_columns)

    def _rebuild_connections_table(self):
        self.cursor.execute("ALTER TABLE connections RENAME TO connections_old")
        self.cursor.execute(
            """
            CREATE TABLE connections
            (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                start_id INTEGER NOT NULL,
                end_id   INTEGER NOT NULL,
                FOREIGN KEY (start_id) REFERENCES items (id) ON DELETE CASCADE,
                FOREIGN KEY (end_id) REFERENCES items (id) ON DELETE CASCADE
            )
            """
        )
        self.cursor.execute(
            """
            INSERT INTO connections (id, start_id, end_id)
            SELECT id, start_id, end_id
            FROM connections_old
            WHERE start_id IN (SELECT id FROM items)
              AND end_id IN (SELECT id FROM items)
            """
        )
        self.cursor.execute("DROP TABLE connections_old")


    def get_salt(self):
        return self.get_metadata("auth_salt")

    def set_salt(self, salt_bytes):
        self.set_metadata("auth_salt", salt_bytes)

    def get_auth_check(self):
        return self.get_metadata("auth_check")

    def set_auth_check(self, check_bytes):
        self.set_metadata("auth_check", check_bytes)

    def get_metadata(self, key):
        self.cursor.execute("SELECT value FROM metadata WHERE key=?", (key,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def set_metadata(self, key, value, commit=True):
        self.cursor.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        if commit:
            self.conn.commit()

    def get_crypto_version(self):
        value = self.get_metadata("crypto_version")
        if value is None:
            return 1
        if isinstance(value, bytes):
            value = value.decode("ascii")
        return int(value)

    def get_wrapped_data_key(self):
        return self.get_metadata("wrapped_data_key")
