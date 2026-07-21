import os

from ...config import Config


class MediaExportService:
    """Write encrypted media node payloads back to disk."""

    def __init__(self, node_service):
        self._node_service = node_service

    def export_node(self, node_id, path):
        item_info = self._get_item_info(node_id)
        is_chunked = bool(item_info and item_info.is_chunked)
        total_size = int(item_info.total_size) if item_info else 0

        if is_chunked:
            return self._export_chunked(node_id, path, total_size)

        data = self._node_service.get_full_data(node_id)
        if data is None:
            raise ValueError("No data found for this node.")
        with open(path, "wb") as f:
            written = f.write(data)
        if written != len(data):
            raise IOError(f"Incomplete export: expected {len(data)} bytes, wrote {written}")
        return written

    def _export_chunked(self, node_id, path, total_size):
        written = 0
        chunk_count = (total_size + Config.CHUNK_SIZE - 1) // Config.CHUNK_SIZE
        try:
            with open(path, "wb") as f:
                for index in range(chunk_count):
                    data = self._node_service.get_chunk(node_id, index)
                    if data is None:
                        raise ValueError(f"Missing media chunk {index} for node {node_id}")
                    written += f.write(data)
            if written != total_size:
                raise IOError(
                    f"Incomplete export: expected {total_size} bytes, wrote {written}"
                )
            return written
        except Exception:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
            raise

    def _get_item_info(self, node_id):
        if hasattr(self._node_service, "get_item_info"):
            return self._node_service.get_item_info(node_id)
        for item in self._node_service.get_all_items():
            if item.id == node_id:
                return item
        return None
