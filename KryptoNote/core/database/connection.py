import sqlite3


class DatabaseConnection:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._init_db()

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
                                total_size   INTEGER DEFAULT 0
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
            """)

        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks ON media_chunks(item_id, chunk_index)")

        self.conn.commit()

    def get_salt(self):
        self.cursor.execute("SELECT value FROM metadata WHERE key='auth_salt'")
        row = self.cursor.fetchone()
        return row[0] if row else None

    def set_salt(self, salt_bytes):
        self.cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('auth_salt', ?)", (salt_bytes,))
        self.conn.commit()

    def get_auth_check(self):
        self.cursor.execute("SELECT value FROM metadata WHERE key='auth_check'")
        row = self.cursor.fetchone()
        return row[0] if row else None

    def set_auth_check(self, check_bytes):
        self.cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('auth_check', ?)", (check_bytes,))
        self.conn.commit()
