import sqlite3
from ..crypto import CryptoManager
from ...config import Config


class NodeRepository:
    def __init__(self, db_conn, crypto: CryptoManager = None):
        self.conn_manager = db_conn
        self.conn = db_conn.conn
        self.cursor = db_conn.cursor
        self.crypto = crypto

    def add_item(self, item_type, x, y, w, h, title="", text=None, thumb=None, data=None):
        enc_title = self.crypto.encrypt(title.encode()) if title else self.crypto.encrypt(b"Untitled")
        enc_text = self.crypto.encrypt(text.encode()) if text else None
        enc_thumb = self.crypto.encrypt(thumb) if thumb else None
        enc_data = self.crypto.encrypt(data) if data and len(data) < Config.CHUNK_SIZE * 2 else None

        is_chunked = 0
        total_size = len(data) if data else 0

        self.cursor.execute("""
                            INSERT INTO items (type, title, x, y, width, height, text_content, thumbnail, full_data,
                                               is_chunked, total_size)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (item_type, enc_title, x, y, w, h, enc_text, enc_thumb, enc_data, is_chunked, total_size))
        item_id = self.cursor.lastrowid
        self.conn.commit()
        return item_id

    def add_streamed_video(self, item_type, x, y, w, h, title, thumb, file_path):
        enc_title = self.crypto.encrypt(title.encode())
        enc_thumb = self.crypto.encrypt(thumb) if thumb else None
        file_size = 0
        with open(file_path, 'rb') as f:
            f.seek(0, 2)
            file_size = f.tell()

        self.cursor.execute("""
                            INSERT INTO items (type, title, x, y, width, height, thumbnail, is_chunked, total_size)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                            """, (item_type, enc_title, x, y, w, h, enc_thumb, file_size))
        item_id = self.cursor.lastrowid

        with open(file_path, 'rb') as f:
            index = 0
            while True:
                chunk = f.read(Config.CHUNK_SIZE)
                if not chunk: break
                enc_chunk = self.crypto.encrypt(chunk)
                self.cursor.execute("INSERT INTO media_chunks (item_id, chunk_index, data) VALUES (?, ?, ?)",
                                    (item_id, index, enc_chunk))
                index += 1
        self.conn.commit()
        return item_id

    def get_chunk(self, item_id, chunk_index):
        self.cursor.execute("SELECT data FROM media_chunks WHERE item_id=? AND chunk_index=?", (item_id, chunk_index))
        row = self.cursor.fetchone()
        if row:
            return self.crypto.decrypt(row[0])
        return None

    def get_all_items(self):
        self.cursor.execute(
            "SELECT id, type, title, x, y, width, height, text_content, thumbnail, is_chunked, total_size FROM items")
        rows = self.cursor.fetchall()
        decrypted_rows = []
        for r in rows:
            rid, rtype, etitle, x, y, w, h, etext, ethumb, chunked, tsize = r
            if self.crypto:
                dtitle = self.crypto.decrypt(etitle).decode() if etitle else ""
                dtext = self.crypto.decrypt(etext).decode() if etext else ""
                dthumb = self.crypto.decrypt(ethumb) if ethumb else None
            else:
                dtitle = ""
                dtext = ""
                dthumb = None

            decrypted_rows.append({
                'id': rid, 'type': rtype, 'title': dtitle, 'x': x, 'y': y, 'width': w, 'height': h,
                'text': dtext, 'thumbnail': dthumb, 'is_chunked': chunked, 'total_size': tsize
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

    def update_item_title(self, item_id, title):
        enc_title = self.crypto.encrypt(title.encode()) if title \
            else self.crypto.encrypt(b"Untitled")
        self.cursor.execute("UPDATE items SET title=? WHERE id=?", (enc_title, item_id))
        self.conn.commit()

    def delete_item(self, item_id):
        self.delete_node_cascade(item_id)

    def update_text_content(self, item_id, title, new_text):
        enc_title = self.crypto.encrypt(title.encode()) if title \
            else self.crypto.encrypt(b"Untitled")
        enc_text = self.crypto.encrypt(new_text.encode())
        self.cursor.execute("UPDATE items SET title=?, text_content=? WHERE id=?", (enc_title, enc_text, item_id))
        self.conn.commit()

    def add_connection(self, start_id, end_id, commit=True):
        self.cursor.execute("INSERT INTO connections (start_id, end_id) VALUES (?, ?)", (start_id, end_id))
        if commit:
            self.conn.commit()
        return self.cursor.lastrowid

    def commit_changes(self):
        self.conn.commit()

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
            self.cursor.execute("DELETE FROM media_chunks WHERE item_id=?", (item_id,))
            self.cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
