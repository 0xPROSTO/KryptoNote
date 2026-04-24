from .items.media import MediaNode
from .items.text import TextNode
from ...config import Config


class NodeFactory:
    @staticmethod
    def create_node_from_db(data, service):
        item_type = data.type
        if item_type == "text":
            return TextNode(
                item_id=data.id,
                x=data.x,
                y=data.y,
                w=data.width,
                h=data.height,
                title=data.title,
                text=data.text_content,
                service=service,
                title_size=data.title_size,
                text_size=data.text_size,
            )

        elif item_type in ["image", "video"]:
            return MediaNode(
                item_id=data.id,
                x=data.x,
                y=data.y,
                w=data.width,
                h=data.height,
                title=data.title,
                thumbnail_bytes=data.thumbnail,
                service=service,
                media_type=item_type,
                is_chunked=data.is_chunked,
                total_size=data.total_size,
            )

        raise ValueError(f"Unknown node type: {item_type}")

    @staticmethod
    def create_new_text(service, x, y, title):
        w, h = Config.NODE_DEFAULT_WIDTH, Config.NODE_DEFAULT_HEIGHT
        rid = service.add_item("text", x, y, w, h, title=title, text="", title_size=14, text_size=10)
        node = TextNode(rid, x, y, w, h, title, "", service, title_size=14, text_size=10)
        node._auto_fit_pending = True
        return node

    @staticmethod
    def create_new_media(service, x, y, mtype, title, thumb_bytes, full_data=None, file_path=None, progress_callback=None):
        w, h = Config.NODE_MEDIA_SIZE, Config.NODE_MEDIA_SIZE
        if mtype == "video" and file_path:
            rid = service.add_streamed_video(
                mtype, x, y, w, h, title, thumb_bytes, file_path, progress_callback
            )
            import os

            total_size = os.path.getsize(file_path)
            return MediaNode(
                rid, x, y, w, h, title, thumb_bytes, service, mtype, 1, total_size
            )

        else:
            rid = service.add_item(
                mtype, x, y, w, h, title=title, thumb=thumb_bytes, data=full_data
            )
            return MediaNode(rid, x, y, w, h, title, thumb_bytes, service, mtype, 0, 0)
