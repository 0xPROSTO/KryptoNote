from .items.text import TextNode
from .items.media import MediaNode
from ...config import Config


class NodeFactory:
    @staticmethod
    def create_node_from_db(data, repo):
        item_type = data['type']

        if item_type == 'text':
            return TextNode(
                item_id=data['id'],
                x=data['x'],
                y=data['y'],
                w=data['width'],
                h=data['height'],
                title=data['title'],
                text=data['text'],
                repo=repo
            )

        elif item_type in ['image', 'video']:
            return MediaNode(
                item_id=data['id'],
                x=data['x'],
                y=data['y'],
                w=data['width'],
                h=data['height'],
                title=data['title'],
                thumbnail_bytes=data['thumbnail'],
                repo=repo,
                media_type=item_type,
                is_chunked=data['is_chunked'],
                total_size=data['total_size']
            )

        raise ValueError(f"Unknown node type: {item_type}")

    @staticmethod
    def create_new_text(repo, x, y, title):
        w, h = Config.NODE_DEFAULT_WIDTH, Config.NODE_DEFAULT_HEIGHT
        rid = repo.add_item("text", x, y, w, h, title=title, text="")
        return TextNode(rid, x, y, w, h, title, "", repo)

    @staticmethod
    def create_new_media(repo, x, y, mtype, title, thumb_bytes, full_data=None, file_path=None):
        w, h = Config.NODE_MEDIA_SIZE, Config.NODE_MEDIA_SIZE

        if mtype == "video" and file_path:
            rid = repo.add_streamed_video(mtype, x, y, w, h, title, thumb_bytes, file_path)
            import os
            total_size = os.path.getsize(file_path)
            return MediaNode(rid, x, y, w, h, title, thumb_bytes, repo, mtype, 1, total_size)

        else:
            rid = repo.add_item(mtype, x, y, w, h, title=title, thumb=thumb_bytes, data=full_data)
            return MediaNode(rid, x, y, w, h, title, thumb_bytes, repo, mtype, 0, 0)