from ..core.database.models import NodeItemDTO, ConnectionDTO

class NodeService:
    def __init__(self, repo):
        self.repo = repo

    def get_all_items(self) -> list[NodeItemDTO]:
        return self.repo.get_all_items()

    def get_all_connections(self) -> list[ConnectionDTO]:
        return self.repo.get_all_connections()

    def add_item(self, item_type, x, y, w, h, title="", text=None, thumb=None, data=None):
        return self.repo.add_item(item_type, x, y, w, h, title, text, thumb, data)

    def add_streamed_video(self, item_type, x, y, w, h, title, thumb, file_path, progress_callback=None):
        return self.repo.add_streamed_video(item_type, x, y, w, h, title, thumb, file_path, progress_callback)

    def add_connection(self, start_id, end_id, commit=True):
        return self.repo.add_connection(start_id, end_id, commit=commit)

    def delete_node_cascade(self, item_id):
        self.repo.delete_node_cascade(item_id)

    def delete_connection(self, conn_id):
        self.repo.delete_connection(conn_id)

    def update_pos(self, item_id, x, y):
        self.repo.update_pos(item_id, x, y)

    def update_size(self, item_id, w, h):
        self.repo.update_size(item_id, w, h)

    def update_item_title(self, item_id, title):
        self.repo.update_item_title(item_id, title)

    def update_text_content(self, item_id, title, new_text):
        self.repo.update_text_content(item_id, title, new_text)

    def get_chunk(self, item_id, chunk_index):
        return self.repo.get_chunk(item_id, chunk_index)

    def get_full_data(self, item_id):
        return self.repo.get_full_data(item_id)

    def commit_changes(self):
        self.repo.commit_changes()

    def search_items(self, query):
        return self.repo.search_items(query)
