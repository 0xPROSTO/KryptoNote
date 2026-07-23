import os

from PySide6.QtCore import QSettings


class CaseDirectoryService:
    """Persist the case folders available in the project launcher."""

    DIRECTORIES_KEY = "launcher/case_directories"
    ACTIVE_KEY = "launcher/active_case_directory"

    def __init__(
        self,
        default_directory,
        settings=None,
        organization="ZeroXware",
        application="KryptoNote",
    ):
        self.default_directory = self.normalize_path(default_directory)
        self._settings = settings if settings is not None else QSettings(
            organization, application
        )

    @staticmethod
    def normalize_path(path):
        if path is None:
            return ""
        try:
            value = os.fspath(path).strip()
        except (TypeError, ValueError):
            return ""
        if not value:
            return ""
        return os.path.abspath(os.path.normpath(os.path.expanduser(value)))

    @classmethod
    def normalize_directories(cls, directories):
        if isinstance(directories, str):
            directories = [directories]
        result = []
        seen = set()
        for directory in directories or ():
            normalized = cls.normalize_path(directory)
            if not normalized:
                continue
            key = os.path.normcase(normalized)
            if key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result

    def load(self):
        directories = self.normalize_directories(
            self._settings.value(self.DIRECTORIES_KEY, [])
        )
        if not directories:
            directories = [self.default_directory]
        active = self.normalize_path(self._settings.value(self.ACTIVE_KEY, ""))
        active_key = os.path.normcase(active)
        active = next(
            (
                directory
                for directory in directories
                if os.path.normcase(directory) == active_key
            ),
            directories[0],
        )
        return directories, active

    def save(self, directories, active_directory=None):
        directories = self.normalize_directories(directories)
        if not directories:
            directories = [self.default_directory]
        requested_active = self.normalize_path(active_directory)
        active_key = os.path.normcase(requested_active)
        active = next(
            (
                directory
                for directory in directories
                if os.path.normcase(directory) == active_key
            ),
            directories[0],
        )
        self._settings.setValue(self.DIRECTORIES_KEY, directories)
        self._settings.setValue(self.ACTIVE_KEY, active)
        self._settings.sync()
        return directories, active
