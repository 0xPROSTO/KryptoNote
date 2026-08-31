"""Core storage constants with no GUI dependencies.

The sets in this module are deliberately kept free of Qt/Pillow imports.  A
few consumers (the importer and QML model) need to make the same decision
about what constitutes media, so keeping the predicates here avoids subtly
different lists in each layer.
"""

import math


MEDIA_CHUNK_SIZE = 4 * 1024 * 1024
MEBIBYTE = 1024 * 1024

# World geometry is stored as IEEE-754 doubles.  At 2**48 their spacing is
# 0.0625 canvas units, still below one screen pixel at the maximum 5x zoom.
# Beyond this range small interactive edits can no longer be represented
# reliably even though existing coordinates remain readable as finite doubles.
CANVAS_INTERACTIVE_COORDINATE_LIMIT = float(2**48)
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


def is_interactive_canvas_coordinate(value):
    """Return whether *value* is finite and inside the editable world range."""

    try:
        coordinate = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return (
        math.isfinite(coordinate)
        and abs(coordinate) <= CANVAS_INTERACTIVE_COORDINATE_LIMIT
    )


def is_interactive_canvas_position(x, y):
    """Return whether both durable position components remain editable."""

    return (
        is_interactive_canvas_coordinate(x)
        and is_interactive_canvas_coordinate(y)
    )


def clamp_interactive_canvas_coordinate(value):
    """Clamp one finite coordinate to the editable double-precision range."""

    coordinate = float(value)
    if not math.isfinite(coordinate):
        raise ValueError("Canvas coordinate must be finite")
    limit = CANVAS_INTERACTIVE_COORDINATE_LIMIT
    return max(-limit, min(limit, coordinate))


def fit_canvas_group_origin(origin_x, origin_y, relative_positions):
    """Clamp a group origin while preserving every relative node position.

    ``relative_positions`` contains top-left ``(x, y)`` offsets.  Width and
    height stay independent doubles and are intentionally not part of the
    durable-position limit.
    """

    points = [(float(x), float(y)) for x, y in relative_positions]
    if not points:
        return (
            clamp_interactive_canvas_coordinate(origin_x),
            clamp_interactive_canvas_coordinate(origin_y),
        )
    if not all(math.isfinite(value) for point in points for value in point):
        raise ValueError("Canvas group positions must be finite")

    limit = CANVAS_INTERACTIVE_COORDINATE_LIMIT
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    if max_x - min_x > limit * 2 or max_y - min_y > limit * 2:
        raise ValueError("Canvas group is wider than the interactive range")

    origin_x = float(origin_x)
    origin_y = float(origin_y)
    if not math.isfinite(origin_x) or not math.isfinite(origin_y):
        raise ValueError("Canvas group origin must be finite")
    origin_x = max(-limit - min_x, min(limit - max_x, origin_x))
    origin_y = max(-limit - min_y, min(limit - max_y, origin_y))
    return origin_x, origin_y


def is_media_node_type(node_type):
    """Return whether *node_type* is an image, video, or audio node."""

    return str(node_type or "").strip().lower() in MEDIA_NODE_TYPES


def is_playable_node_type(node_type):
    """Return whether *node_type* has an inline media playback surface."""

    return str(node_type or "").strip().lower() in PLAYABLE_NODE_TYPES
