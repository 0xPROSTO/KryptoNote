import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


class DatabaseConnection:
    @staticmethod
    def read_metadata_readonly(db_path, key):
        """Read metadata without creating or migrating the database file."""
        path = Path(db_path).resolve()
        wal_path = Path(f"{path}-wal")
        has_pending_wal = wal_path.is_file() and wal_path.stat().st_size > 0
        query = "mode=ro" if has_pending_wal else "mode=ro&immutable=1"
        uri = f"{path.as_uri()}?{query}"
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key=?", (key,)
            ).fetchone()
        return row[0] if row else None

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._closed = False
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self.cursor = self.conn.cursor()
        try:
            self._init_db()
        except Exception:
            self.conn.close()
            raise

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

    def _init_db(self):
        self.cursor.execute("PRAGMA journal_mode=WAL;")
        self.cursor.execute("PRAGMA synchronous=NORMAL;")
        self.cursor.execute("PRAGMA temp_store=MEMORY;")

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
                                media_duration REAL DEFAULT 0
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
        self._migrate_db()
        self._migrate_tag_schema()
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_item_tags_tag ON item_tags(tag_id)")
        self._migrate_relational_constraints()
        self.conn.commit()

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

    def _migrate_db(self):
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

        now = datetime.now().isoformat(timespec="seconds")
        self.cursor.execute("UPDATE items SET created_at=? WHERE created_at IS NULL OR created_at=''", (now,))
        self.cursor.execute("UPDATE items SET updated_at=created_at WHERE updated_at IS NULL OR updated_at=''")

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
