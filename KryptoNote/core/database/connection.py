import sqlite3
from datetime import datetime


class DatabaseConnection:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        try:
            self._init_db()
        except Exception:
            self.conn.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
        return False

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
            "CREATE TABLE IF NOT EXISTS connections (id INTEGER PRIMARY KEY AUTOINCREMENT, start_id INTEGER, end_id INTEGER)"
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS media_chunks
            (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id     INTEGER,
                chunk_index INTEGER,
                data        BLOB,
                FOREIGN KEY (item_id) REFERENCES items (id)
            )
            """
        )

        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks ON media_chunks(item_id, chunk_index)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_conn_start ON connections(start_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_conn_end ON connections(end_id)")
        self._migrate_db()
        self.conn.commit()

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
