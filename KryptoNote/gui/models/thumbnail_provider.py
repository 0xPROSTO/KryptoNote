"""
ThumbnailProvider — QQuickImageProvider for serving node thumbnails to QML.
QML Image elements request thumbnails via: "image://thumbnails/<node_id>"
"""

from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtGui import QImage


class ThumbnailProvider(QQuickImageProvider):
    def __init__(self, node_model):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._node_model = node_model

    def requestImage(self, id_str, size, requested_size):
        """
        Called by QML when Image { source: "image://thumbnails/123" } is used.
        id_str will be the node ID as string.
        """
        try:
            node_id = int(id_str)
        except ValueError:
            return QImage()

        data = self._node_model.get_node_data(node_id)
        if data is None or data.get("thumbnail") is None:
            return QImage()

        image = data["thumbnail"]
        if isinstance(image, QImage) and not image.isNull():
            if requested_size.isValid() and requested_size.width() > 0:
                image = image.scaled(
                    requested_size.width(),
                    requested_size.height(),
                    mode=1,  # KeepAspectRatio
                    transformMode=1,  # SmoothTransformation
                )
            return image

        return QImage()
