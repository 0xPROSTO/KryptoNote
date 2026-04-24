from .models import NodeItemDTO, ConnectionDTO
from ..crypto import CryptoManager
from ...config import Config


class NodeRepository:
    def __init__(self, db_conn, crypto: CryptoManager = None):
        self.conn_manager = db_conn
        self.conn = db_conn.conn
        self.cursor = db_conn.cursor
        self.crypto = crypto

    def add_item(
            self, item_type, x, y, w, h, title="", text=None, thumb=None, data=None, title_size=14, text_size=10
    ):
        enc_title = self.crypto.encrypt((title or "").encode())
        enc_text = self.crypto.encrypt(text.encode()) if text else None
        enc_thumb = self.crypto.encrypt(thumb) if thumb else None
        enc_data = self.crypto.encrypt(data) if data else None
        is_chunked = 0
        total_size = len(data) if data else 0

        self.cursor.execute("""
                            INSERT INTO items (type, title, x, y, width, height, text_content, thumbnail, full_data,
                                               is_chunked, total_size, title_size, text_size)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (item_type, enc_title, x, y, w, h, enc_text, enc_thumb, enc_data, is_chunked, total_size,
                             title_size, text_size))
        item_id = self.cursor.lastrowid
        self.conn.commit()
        return item_id

    def add_streamed_video(self, item_type, x, y, w, h, title, thumb, file_path, progress_callback=None):
        enc_title = self.crypto.encrypt(title.encode())
        enc_thumb = self.crypto.encrypt(thumb) if thumb else None
        with open(file_path, "rb") as f:
            f.seek(0, 2)
            file_size = f.tell()

        total_chunks = (file_size + Config.CHUNK_SIZE - 1) // Config.CHUNK_SIZE if file_size > 0 else 1

        self.cursor.execute("""
                            INSERT INTO items (type, title, x, y, width, height, thumbnail, is_chunked, total_size)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                            """, (item_type, enc_title, x, y, w, h, enc_thumb, file_size))
        item_id = self.cursor.lastrowid
        with open(file_path, "rb") as f:
            index = 0
            while True:
                chunk = f.read(Config.CHUNK_SIZE)
                if not chunk:
                    break
                if progress_callback:
                    progress_callback(index + 1, total_chunks, "Encrypting")

                enc_chunk = self.crypto.encrypt(chunk)
                self.cursor.execute(
                    "INSERT INTO media_chunks (item_id, chunk_index, data) VALUES (?, ?, ?)",
                    (item_id, index, enc_chunk),
                )

                index += 1
                if index % 25 == 0:
                    if progress_callback:
                        progress_callback(index, total_chunks, "Writing to disk")

                    self.conn.commit()

        if progress_callback:
            progress_callback(total_chunks, total_chunks, "Finalizing")

        self.conn.commit()
        return item_id

    def get_chunk(self, item_id, chunk_index):
        self.cursor.execute(
            "SELECT data FROM media_chunks WHERE item_id=? AND chunk_index=?",
            (item_id, chunk_index),
        )
        row = self.cursor.fetchone()
        if row:
            return self.crypto.decrypt(row[0])

        return None

    def get_all_items(self):
        self.cursor.execute(
            "SELECT id, type, title, x, y, width, height, text_content, thumbnail, is_chunked, total_size, title_size, text_size FROM items"
        )

        rows = self.cursor.fetchall()
        decrypted_rows = []
        for r in rows:
            rid, rtype, etitle, x, y, w, h, etext, ethumb, chunked, tsize, tsize_val, text_size_val = r
            if self.crypto:
                dtitle = self.crypto.decrypt(etitle).decode() if etitle else ""
                dtext = self.crypto.decrypt(etext).decode() if etext else ""
                dthumb = self.crypto.decrypt(ethumb) if ethumb else None

            else:
                dtitle = ""
                dtext = ""
                dthumb = None

            decrypted_rows.append(NodeItemDTO(
                id=rid, type=rtype, title=dtitle, x=x, y=y, width=w, height=h,
                text_content=dtext, thumbnail=dthumb, is_chunked=bool(chunked), total_size=tsize,
                title_size=tsize_val, text_size=text_size_val
            ))
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
        self.cursor.execute(
            "UPDATE items SET width=?, height=? WHERE id=?", (w, h, item_id)
        )
        self.conn.commit()

    def update_item_title(self, item_id, title):
        enc_title = self.crypto.encrypt((title or "").encode())
        self.cursor.execute("UPDATE items SET title=? WHERE id=?", (enc_title, item_id))
        self.conn.commit()

    def delete_item(self, item_id):
        self.delete_node_cascade(item_id)

    def update_text_content(self, item_id, title, new_text, title_size=14, text_size=10):
        enc_title = self.crypto.encrypt((title or "").encode())
        enc_text = self.crypto.encrypt(new_text.encode())
        self.cursor.execute(
            "UPDATE items SET title=?, text_content=?, title_size=?, text_size=? WHERE id=?",
            (enc_title, enc_text, title_size, text_size, item_id),
        )
        self.conn.commit()

    def add_connection(self, start_id, end_id, commit=True):
        self.cursor.execute(
            "INSERT INTO connections (start_id, end_id) VALUES (?, ?)",
            (start_id, end_id),
        )
        if commit:
            self.conn.commit()

        return self.cursor.lastrowid

    def commit_changes(self):
        self.conn.commit()

    def get_all_connections(self):
        self.cursor.execute("SELECT id, start_id, end_id FROM connections")
        rows = self.cursor.fetchall()
        return [ConnectionDTO(id=r[0], start_id=r[1], end_id=r[2]) for r in rows]

    def delete_connection(self, conn_id):
        self.cursor.execute("DELETE FROM connections WHERE id=?", (conn_id,))
        self.conn.commit()

    def delete_node_cascade(self, item_id):
        self.cursor.execute("SELECT type, total_size FROM items WHERE id=?", (item_id,))
        row = self.cursor.fetchone()
        self.cursor.fetchall()

        should_vacuum = False
        if row:
            item_type, total_size = row
            if item_type == "video" or (total_size and total_size > 10 * 1024 * 1024):
                should_vacuum = True

        db_path = getattr(self.conn_manager, "db_path", ":memory:")

        if db_path == ":memory:":
            self.cursor.execute("DELETE FROM connections WHERE start_id=? OR end_id=?", (item_id, item_id))
            self.cursor.execute("DELETE FROM media_chunks WHERE item_id=?", (item_id,))
            self.cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
            self.conn.commit()
            if should_vacuum:
                self.conn.execute("VACUUM")
        else:
            try:
                from PySide6.QtWidgets import QApplication
                import sqlite3
                import concurrent.futures
                import threading

                if not hasattr(self, '_delete_executor'):
                    self._delete_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    self._active_deletions = 0
                    self._del_lock = threading.Lock()

                app = QApplication.instance()

                def get_main_window():
                    if not app: return None
                    for w in app.topLevelWidgets():
                        if w.inherits("QMainWindow"):
                            return w
                    return None

                main_win = get_main_window()

                if should_vacuum:
                    with self._del_lock:
                        self._active_deletions += 1
                        if main_win and hasattr(main_win, 'progress_bar') and hasattr(main_win, 'view'):
                            view = main_win.view
                            if not hasattr(app, 'global_dim_overlay') or not app.global_dim_overlay:
                                from KryptoNote.gui.widgets.overlays.dim_overlay import DimOverlay
                                app.global_dim_overlay = DimOverlay(view, block_input=True)
                                app.global_dim_overlay.setParent(view)
                                app.global_dim_overlay.resize(view.size())
                            app.global_dim_overlay.show()
                            app.global_dim_overlay.raise_()
                            msg = "Cleaning and optimizing database..."
                            main_win.progress_bar.start(msg, indeterminate=True)
                            if hasattr(main_win, 'progress_label'):
                                main_win.progress_label.setText(msg)
                                main_win.progress_label.setVisible(True)
                                main_win.status_label.setVisible(False)
                            app.processEvents()

                def run_delete_and_vac():
                    try:
                        v_conn = sqlite3.connect(db_path, timeout=60.0)
                        v_cursor = v_conn.cursor()
                        v_cursor.execute("PRAGMA journal_mode=WAL;")
                        v_cursor.execute("DELETE FROM connections WHERE start_id=? OR end_id=?", (item_id, item_id))
                        v_cursor.execute("DELETE FROM media_chunks WHERE item_id=?", (item_id,))
                        v_cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
                        v_conn.commit()
                        if should_vacuum:
                            v_conn.execute("VACUUM")
                        v_conn.close()
                    except Exception as e:
                        print(f"Background Delete/Vacuum Error: {e}")
                    finally:
                        if should_vacuum:
                            with self._del_lock:
                                self._active_deletions -= 1
                                if self._active_deletions == 0:
                                    def update_ui():
                                        try:
                                            mw = get_main_window()
                                            if mw:
                                                if hasattr(mw, 'progress_bar'):
                                                    mw.progress_bar.finish()
                                                if hasattr(mw, 'progress_label'):
                                                    mw.progress_label.setVisible(False)
                                                    mw.status_label.setVisible(True)
                                                    mw.status_label.setText("Ready")
                                                if hasattr(app, 'global_dim_overlay') and app.global_dim_overlay:
                                                    app.global_dim_overlay.fade_out()
                                                    app.global_dim_overlay = None
                                        except Exception as ex:
                                            print(f"update_ui Exception: {ex}")

                                    from PySide6.QtCore import QTimer
                                    QTimer.singleShot(0, app, update_ui)

                self._delete_executor.submit(run_delete_and_vac)
            except Exception as e:
                print(f"CRASH IN DELETE_NODE_CASCADE: {e}")
                self.conn.rollback()

    def search_items(self, query):
        all_items = self.get_all_items()
        results = []
        q = query.lower()
        for item in all_items:
            title_match = q in item.title.lower() if item.title else False
            text_match = q in item.text_content.lower() if item.text_content else False

            if title_match or text_match:
                results.append(item)

        return results
