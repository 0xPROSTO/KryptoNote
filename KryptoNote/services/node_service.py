from ..core.database.models import NodeItemDTO, ConnectionDTO


class NodeService:
    def __init__(self, repo):
        self.repo = repo

    def get_all_items(self) -> list[NodeItemDTO]:
        return self.repo.get_all_items()

    def search_items(self, query: str) -> list[NodeItemDTO]:
        """In-memory search across decrypted node titles and text content."""
        q = query.lower()
        return [
            item for item in self.repo.get_all_items()
            if q in (item.title or "").lower() or q in (item.text_content or "").lower()
        ]

    def get_all_connections(self) -> list[ConnectionDTO]:
        return self.repo.get_all_connections()

    def add_item(
            self, item_type, x, y, w, h, title="", text=None, thumb=None,
            data=None, title_size=14, text_size=10, media_width=0,
            media_height=0, media_duration=0.0
    ):
        return self.repo.add_item(
            item_type, x, y, w, h, title, text, thumb, data, title_size,
            text_size, media_width, media_height, media_duration
        )

    def add_streamed_media(
            self, item_type, x, y, w, h, title, thumb, file_path,
            progress_callback=None, media_width=0, media_height=0,
            media_duration=0.0
    ):
        return self.repo.add_streamed_media(
            item_type, x, y, w, h, title, thumb, file_path, progress_callback,
            media_width, media_height, media_duration
        )

    def add_connection(self, start_id, end_id, commit=True):
        return self.repo.add_connection(start_id, end_id, commit=commit)

    def delete_node_cascade(
            self,
            item_id,
            on_start_vacuum=None,
            on_finish_vacuum=None,
            on_waiting_lock=None,
    ):
        self.repo.delete_node_cascade(
            item_id,
            on_start_vacuum,
            on_finish_vacuum,
            on_waiting_lock,
        )

    def delete_nodes_cascade(
            self,
            item_ids,
            on_start_vacuum=None,
            on_finish_vacuum=None,
            on_waiting_lock=None,
    ):
        self.repo.delete_nodes_cascade(
            item_ids,
            on_start_vacuum,
            on_finish_vacuum,
            on_waiting_lock,
        )

    def delete_connection(self, conn_id):
        self.repo.delete_connection(conn_id)

    def update_pos(self, item_id, x, y):
        self.repo.update_pos(item_id, x, y)

    def update_size(self, item_id, w, h):
        self.repo.update_size(item_id, w, h)

    def update_item_title(self, item_id, title):
        self.repo.update_item_title(item_id, title)

    def update_text_content(self, item_id, title, new_text, title_size=14, text_size=10):
        self.repo.update_text_content(item_id, title, new_text, title_size, text_size)

    def get_chunk(self, item_id, chunk_index):
        return self.repo.get_chunk(item_id, chunk_index)

    def get_full_data(self, item_id):
        return self.repo.get_full_data(item_id)

    def get_item_info(self, item_id):
        return self.repo.get_item_info(item_id)

    def get_item_data(self, item_id):
        item = self.get_item_info(item_id)
        if item and item.is_chunked and item.total_size > 0:
            chunks = []
            chunk_index = 0
            while True:
                chunk = self.get_chunk(item_id, chunk_index)
                if not chunk:
                    break
                chunks.append(chunk)
                chunk_index += 1
            return b"".join(chunks)
        return self.get_full_data(item_id)

    def commit_changes(self):
        self.repo.commit_changes()

    def vacuum_database(
            self,
            on_start_vacuum=None,
            on_finish_vacuum=None,
            on_waiting_lock=None,
    ):
        self.repo.vacuum_database(
            on_start_vacuum,
            on_finish_vacuum,
            on_waiting_lock,
        )

    def get_db_path(self):
        return getattr(self.repo.conn_manager, "db_path", None)

    def create_crypto_clone(self):
        """Create a new CryptoManager with the same key for thread-safe use.

        Returns a full CryptoManager instance instead of raw key bytes
        to prevent secret leakage through the service API.
        """
        return self.repo.crypto.create_clone()
