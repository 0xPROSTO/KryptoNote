from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtQml import QQmlNetworkAccessManagerFactory


class RestrictedQmlNetworkAccessManager(QNetworkAccessManager):
    """Allow only bundled QML resources and explicitly trusted local files."""

    _SAFE_SCHEMES = {"qrc", "image", "data"}

    def __init__(self, trusted_roots, parent=None):
        super().__init__(parent)
        self._trusted_roots = tuple(
            Path(root).resolve(strict=False) for root in trusted_roots
        )

    def _is_trusted_local_file(self, url):
        if url.host():
            return False
        local_path = url.toLocalFile()
        if not local_path:
            return False
        candidate = Path(local_path).resolve(strict=False)
        return any(
            candidate == root or root in candidate.parents
            for root in self._trusted_roots
        )

    def createRequest(self, operation, request, outgoing_data=None):
        url = request.url()
        scheme = url.scheme().lower()
        allowed = scheme in self._SAFE_SCHEMES
        if scheme == "file":
            allowed = self._is_trusted_local_file(url)

        if not allowed:
            blocked_request = QNetworkRequest(request)
            blocked_request.setUrl(QUrl("blocked://qml-network-policy"))
            request = blocked_request

        return super().createRequest(operation, request, outgoing_data)


class RestrictedQmlNetworkAccessManagerFactory(QQmlNetworkAccessManagerFactory):
    def __init__(self, trusted_roots):
        super().__init__()
        self._trusted_roots = tuple(trusted_roots)
        self._managers = []

    def create(self, parent):
        manager = RestrictedQmlNetworkAccessManager(self._trusted_roots, parent)
        # Keep Python wrappers alive for the lifetime of the QML engine.
        self._managers.append(manager)
        return manager
