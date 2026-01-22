import sqlite3
from .crypto import CryptoManager


class Storage:
    def __init__(self, db_path, crypto: CryptoManager = None):
        self.conn = sqlite3.connect(db_path)
        self.crypto = crypto
        self.cursor = self.conn.cursor()
        self._init_db()

    def _init_db(self):
        self.cursor.execute("""
                            CREATE TABLE IF NOT EXISTS metadata
                            (
                                key   TEXT PRIMARY KEY,
                                value BLOB
                            )
                            """)

        self.cursor.execute("""
                            CREATE TABLE IF NOT EXISTS items
                            (
                                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                                type         TEXT,
                                x            REAL,
                                y            REAL,
                                width        REAL,
                                height       REAL,
                                text_content BLOB,
                                thumbnail    BLOB,
                                full_data    BLOB
                            )
                            """)
        self.cursor.execute("""
                            CREATE TABLE IF NOT EXISTS connections
                            (
                                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                                start_id INTEGER,
                                end_id   INTEGER
                            )
                            """)

        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_conn_start ON connections(start_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_conn_end ON connections(end_id)")

        self.conn.commit()

    def get_salt(self):
        self.cursor.execute("SELECT value FROM metadata WHERE key='auth_salt'")
        row = self.cursor.fetchone()
        return row[0] if row else None

    def set_salt(self, salt_bytes):
        self.cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('auth_salt', ?)", (salt_bytes,))
        self.conn.commit()

    def add_item(self, item_type, x, y, w, h, text=None, thumb=None, data=None):
        enc_text = self.crypto.encrypt(text.encode()) if text else None
        enc_thumb = self.crypto.encrypt(thumb) if thumb else None
        enc_data = self.crypto.encrypt(data) if data else None

        self.cursor.execute("""
                            INSERT INTO items (type, x, y, width, height, text_content, thumbnail, full_data)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (item_type, x, y, w, h, enc_text, enc_thumb, enc_data))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_all_items(self):
        self.cursor.execute("SELECT id, type, x, y, width, height, text_content, thumbnail FROM items")
        rows = self.cursor.fetchall()
        decrypted_rows = []
        for r in rows:
            rid, rtype, x, y, w, h, etext, ethumb = r
            if self.crypto:
                dtext = self.crypto.decrypt(etext).decode() if etext else ""
                dthumb = self.crypto.decrypt(ethumb) if ethumb else None
            else:
                dtext = ""
                dthumb = None

            decrypted_rows.append({
                'id': rid, 'type': rtype, 'x': x, 'y': y, 'w': w, 'h': h,
                'text': dtext, 'thumbnail': dthumb
            })
        return decrypted_rows

    def get_full_data(self, item_id):
        self.cursor.execute("SELECT full_data FROM items WHERE id=?", (item_id,))
        row = self.cursor.fetchone()
        if row and row[0]:
            return self.crypto.decrypt(row[0])
        return None

    def update_pos(self, item_id, x, y):
        self.cursor.execute("UPDATE items SET x=?, y=? WHERE id=?", (x, y, item_id))
        self.conn.commit()

    def update_size(self, item_id, w, h):
        self.cursor.execute("UPDATE items SET width=?, height=? WHERE id=?", (w, h, item_id))
        self.conn.commit()

    def delete_item(self, item_id):
        self.cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
        self.conn.commit()

    def update_text_content(self, item_id, new_text):
        enc_text = self.crypto.encrypt(new_text.encode())
        self.cursor.execute("UPDATE items SET text_content=? WHERE id=?", (enc_text, item_id))
        self.conn.commit()


    def add_connection(self, start_id, end_id):
        self.cursor.execute("INSERT INTO connections (start_id, end_id) VALUES (?, ?)", (start_id, end_id))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_all_connections(self):
        self.cursor.execute("SELECT id, start_id, end_id FROM connections")
        rows = self.cursor.fetchall()
        return [{'id': r[0], 'start_id': r[1], 'end_id': r[2]} for r in rows]

    def delete_connection(self, conn_id):
        self.cursor.execute("DELETE FROM connections WHERE id=?", (conn_id,))
        self.conn.commit()

    def delete_node_cascade(self, item_id):
        try:
            self.cursor.execute("DELETE FROM connections WHERE start_id=? OR end_id=?", (item_id, item_id))
            self.cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
            self.conn.commit()

        except Exception as e:
            self.conn.rollback()
            print(f"DB Error during cascade delete: {e}")
            raise e
