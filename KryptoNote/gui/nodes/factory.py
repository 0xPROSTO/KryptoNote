from .items.media import MediaNode
from .items.text import TextNode
from .components.auto_fit import AutoFitComponent
from .components.lod import LodComponent
from .components.editor import EditorComponent, MediaActionComponent
from ...config import Config


class NodeFactory:
    @staticmethod
    def _attach_text_components(node):
        node.add_component(LodComponent())
        node.add_component(AutoFitComponent())
        node.add_component(EditorComponent(editor_type="text"))
        
    @staticmethod
    def _attach_media_components(node):
        node.add_component(LodComponent())
        node.add_component(MediaActionComponent())
        node.add_component(AutoFitComponent(min_width=150, max_width=1250, min_height=100, max_height=1250))

    @staticmethod
    def create_node_from_db(data, service):
        item_type = data.type
        if item_type == "text":
            node = TextNode(
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
            NodeFactory._attach_text_components(node)
            return node

        elif item_type in ["image", "video"]:
            node = MediaNode(
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
            NodeFactory._attach_media_components(node)
            return node

        raise ValueError(f"Unknown node type: {item_type}")

    @staticmethod
    def create_new_text(service, x, y, title):
        w, h = Config.NODE_DEFAULT_WIDTH, Config.NODE_DEFAULT_HEIGHT
        rid = service.add_item("text", x, y, w, h, title=title, text="", title_size=14, text_size=10)
        node = TextNode(rid, x, y, w, h, title, "", service, title_size=14, text_size=10)
        NodeFactory._attach_text_components(node)
        node.dispatch_event("set_auto_fit_pending", pending=True)
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
            node = MediaNode(
                rid, x, y, w, h, title, thumb_bytes, service, mtype, 1, total_size
            )
            NodeFactory._attach_media_components(node)
            node.dispatch_event("auto_fit")
            return node

        else:
            rid = service.add_item(
                mtype, x, y, w, h, title=title, thumb=thumb_bytes, data=full_data
            )
            node = MediaNode(rid, x, y, w, h, title, thumb_bytes, service, mtype, 0, 0)
            NodeFactory._attach_media_components(node)
            node.dispatch_event("auto_fit")
            return node
