"""Core storage constants with no GUI dependencies.

The sets in this module are deliberately kept free of Qt/Pillow imports.  A
few consumers (the importer and QML model) need to make the same decision
about what constitutes media, so keeping the predicates here avoids subtly
different lists in each layer.
"""


MEDIA_CHUNK_SIZE = 4 * 1024 * 1024
MEBIBYTE = 1024 * 1024
VACUUM_THRESHOLD_OPTIONS_BYTES = tuple(
    value * MEBIBYTE
    for value in (0, 10, 25, 50, 100, 200, 500, 1024, 2048, 5120, 10240)
)
DEFAULT_VACUUM_THRESHOLD_BYTES = 10 * MEBIBYTE
# Compatibility name for older callers. The policy now compares this value
# with SQLite's reusable page space, not with the deleted item's size.
AUTO_VACUUM_THRESHOLD_BYTES = DEFAULT_VACUUM_THRESHOLD_BYTES

# Extensions understood without probing the platform multimedia backend.
# ``QMediaFormat`` may expose additional formats at runtime; the importer
# augments ``AUDIO_EXTENSIONS`` with those values when Qt is available.
IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp",
})
VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".avi", ".mkv", ".mov", ".webm",
})
AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac",
})

# Aliases make the intent explicit for callers that distinguish a file suffix
# set from a node type set while preserving one source of truth.
IMAGE_FILE_EXTENSIONS = IMAGE_EXTENSIONS
VIDEO_FILE_EXTENSIONS = VIDEO_EXTENSIONS
AUDIO_FILE_EXTENSIONS = AUDIO_EXTENSIONS

MEDIA_NODE_TYPES = frozenset({"image", "video", "audio"})
PLAYABLE_NODE_TYPES = frozenset({"video", "audio"})


def is_media_node_type(node_type):
    """Return whether *node_type* is an image, video, or audio node."""

    return str(node_type or "").strip().lower() in MEDIA_NODE_TYPES


def is_playable_node_type(node_type):
    """Return whether *node_type* has an inline media playback surface."""

    return str(node_type or "").strip().lower() in PLAYABLE_NODE_TYPES
