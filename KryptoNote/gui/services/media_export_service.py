from ...config import Config


class MediaExportService:
    """Write encrypted media node payloads back to disk."""

    def __init__(self, node_service):
        self._node_service = node_service

    def export_node(self, node_id, path):
        item_info = self._get_item_info(node_id)
        is_chunked = bool(item_info and item_info.is_chunked)
        total_size = int(item_info.total_size) if item_info else 0

        if is_chunked and total_size > 0:
            return self._export_chunked(node_id, path, total_size)

        data = self._node_service.get_full_data(node_id)
        if data is None:
            raise ValueError("No data found for this node.")
        with open(path, "wb") as f:
            f.write(data)
        return len(data)

    def _export_chunked(self, node_id, path, total_size):
        written = 0
        chunk_count = (total_size + Config.CHUNK_SIZE - 1) // Config.CHUNK_SIZE
        with open(path, "wb") as f:
            for index in range(chunk_count):
                data = self._node_service.get_chunk(node_id, index)
                if data:
                    f.write(data)
                    written += len(data)
        return written

    def _get_item_info(self, node_id):
        if hasattr(self._node_service, "get_item_info"):
            return self._node_service.get_item_info(node_id)
        for item in self._node_service.get_all_items():
            if item.id == node_id:
                return item
        return None
