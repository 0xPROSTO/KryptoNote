import os
import re

from PySide6.QtCore import QSettings


class CaseDirectoryService:
    """Persist the case folders available in the project launcher."""

    DIRECTORIES_KEY = "launcher/case_directories"
    ACTIVE_KEY = "launcher/active_case_directory"
    _INVALID_PROJECT_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
    _RESERVED_PROJECT_STEMS = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }

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
    def resolve_project_path(cls, base_directory, project_name):
        raw_name = os.fspath(project_name)
        if not raw_name or raw_name != raw_name.strip():
            raise ValueError(
                "Project name cannot start or end with whitespace"
            )
        if raw_name in {".", ".."} or raw_name.endswith((".", " ")):
            raise ValueError("Invalid project name")
        if cls._INVALID_PROJECT_CHARS.search(raw_name):
            raise ValueError(
                "Project name contains characters reserved by Windows"
            )
        filename = (
            raw_name if raw_name.lower().endswith(".zrx")
            else f"{raw_name}.zrx"
        )
        if filename.lower() == ".zrx":
            raise ValueError("Project name cannot be empty")
        stem = os.path.splitext(filename)[0].upper()
        if stem in cls._RESERVED_PROJECT_STEMS:
            raise ValueError("This project name is reserved by Windows")

        base_path = os.path.realpath(cls.normalize_path(base_directory))
        project_path = os.path.realpath(os.path.join(base_path, filename))
        if os.path.normcase(os.path.dirname(project_path)) != os.path.normcase(
            base_path
        ):
            raise ValueError(
                "Project must be created inside the selected case folder"
            )
        return project_path

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
