"""Demand-driven thumbnail provider with a bounded decoded-image cache."""

import threading
from collections import OrderedDict

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


class ThumbnailProvider(QQuickImageProvider):
    DEFAULT_CACHE_BYTES = 64 * 1024 * 1024

    def __init__(self, node_model, service=None, max_cache_bytes=DEFAULT_CACHE_BYTES):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._node_model = node_model
        self._service = service
        self._max_cache_bytes = max(0, int(max_cache_bytes))
        self._cache = OrderedDict()
        self._cache_bytes = 0
        self._lock = threading.RLock()

    def requestImage(self, id_str, size, requested_size):
        try:
            node_id = int(id_str)
        except ValueError:
            return QImage()

        image = self._cached_image(node_id)
        if image.isNull():
            return image
        if size is not None:
            size.setWidth(image.width())
            size.setHeight(image.height())
        if requested_size.isValid() and (
            requested_size.width() > 0 or requested_size.height() > 0
        ):
            width = requested_size.width() if requested_size.width() > 0 else image.width()
            height = (
                requested_size.height()
                if requested_size.height() > 0 else image.height()
            )
            return image.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return image

    def _cached_image(self, node_id):
        with self._lock:
            cached = self._cache.pop(node_id, None)
            if cached is not None:
                self._cache[node_id] = cached
                return cached

            node = self._node_model.get_node_data(node_id)
            image = node.get("thumbnail") if node else None
            if not isinstance(image, QImage) or image.isNull():
                try:
                    payload = (
                        self._service.read_thumbnail(node_id)
                        if self._service is not None else None
                    )
                except Exception:
                    payload = None
                image = QImage.fromData(payload) if payload else QImage()
            if image.isNull():
                return QImage()
            self._insert_cache(node_id, image)
            return image

    def _insert_cache(self, node_id, image):
        image_bytes = max(0, int(image.sizeInBytes()))
        if image_bytes > self._max_cache_bytes:
            return
        while self._cache and self._cache_bytes + image_bytes > self._max_cache_bytes:
            _old_id, old_image = self._cache.popitem(last=False)
            self._cache_bytes -= max(0, int(old_image.sizeInBytes()))
        self._cache[node_id] = image
        self._cache_bytes += image_bytes

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._cache_bytes = 0
