"""Shared connection routing geometry for the canvas and exports."""

from __future__ import annotations

import math


DEFAULT_CONNECTION_STYLE = "curved"
DEFAULT_CONNECTION_PATTERN = "solid"
DEFAULT_CONNECTION_CURVE_FORMULA = "horizontal"
DEFAULT_CONNECTION_CORNER_STYLE = "smooth"
DEFAULT_CONNECTION_ANCHOR_MODE = "perimeter"

CONNECTION_STYLES = ("curved", "straight", "orthogonal", "angled")
CONNECTION_PATTERNS = ("solid", "dashed", "dotted")
CONNECTION_CURVE_FORMULAS = ("horizontal", "adaptive", "s_curve", "arc")
CONNECTION_CORNER_STYLES = ("sharp", "tight", "smooth")
CONNECTION_ANCHOR_MODES = ("perimeter", "side_centers")
CONNECTION_CORNER_RADII = {
    "sharp": 0.0,
    "tight": 8.0,
    "smooth": 24.0,
}
CORNERED_CONNECTION_STYLES = frozenset(("orthogonal", "angled"))

_MAX_SEGMENT_LENGTH = 24.0
_MAX_CURVE_SEGMENTS = 64
_EPSILON = 1e-6


def corner_style_from_legacy_radius(value):
    try:
        radius = float(value)
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_CONNECTION_CORNER_STYLE
    if not math.isfinite(radius):
        return DEFAULT_CONNECTION_CORNER_STYLE
    if radius <= 0.0:
        return "sharp"
    if radius <= 12.0:
        return "tight"
    return "smooth"


def connection_path_commands(
    style,
    start_x,
    start_y,
    end_x,
    end_y,
    curve_formula=DEFAULT_CONNECTION_CURVE_FORMULA,
    corner_style=DEFAULT_CONNECTION_CORNER_STYLE,
    geometry_scale=1.0,
):
    """Return portable M/L/Q/C commands for one routed connection."""
    style = str(style).lower()
    if style not in CONNECTION_STYLES:
        style = DEFAULT_CONNECTION_STYLE

    start = (float(start_x), float(start_y))
    end = (float(end_x), float(end_y))
    geometry_scale = max(0.0, float(geometry_scale))
    if style == "curved":
        return _curved_commands(
            start,
            end,
            curve_formula,
            geometry_scale,
        )
    if style == "straight":
        return [("M", *start), ("L", *end)]

    if corner_style not in CONNECTION_CORNER_STYLES:
        corner_style = DEFAULT_CONNECTION_CORNER_STYLE
    points = _route_points(style, start, end, geometry_scale)
    return _rounded_polyline_commands(
        points,
        CONNECTION_CORNER_RADII[corner_style] * geometry_scale,
    )


def connection_segments(
    style,
    start_x,
    start_y,
    end_x,
    end_y,
    curve_formula=DEFAULT_CONNECTION_CURVE_FORMULA,
    corner_style=DEFAULT_CONNECTION_CORNER_STYLE,
    geometry_scale=1.0,
):
    """Flatten a routed connection for fast spatial hit testing."""
    return flatten_path(
        connection_path_commands(
            style,
            start_x,
            start_y,
            end_x,
            end_y,
            curve_formula,
            corner_style,
            geometry_scale,
        )
    )


def flatten_path(commands):
    """Flatten portable path commands into line segments."""
    segments = []
    current = None
    for command in commands:
        kind = command[0]
        if kind == "M":
            current = (command[1], command[2])
            continue
        if current is None:
            continue
        if kind == "L":
            target = (command[1], command[2])
            _append_segment(segments, current, target)
            current = target
            continue
        if kind == "Q":
            control = (command[1], command[2])
            target = (command[3], command[4])
            estimated = _distance(current, control) + _distance(control, target)
            steps = max(3, min(24, math.ceil(estimated / _MAX_SEGMENT_LENGTH)))
            previous = current
            for index in range(1, steps + 1):
                t = index / steps
                mt = 1.0 - t
                point = (
                    mt * mt * current[0]
                    + 2.0 * mt * t * control[0]
                    + t * t * target[0],
                    mt * mt * current[1]
                    + 2.0 * mt * t * control[1]
                    + t * t * target[1],
                )
                _append_segment(segments, previous, point)
                previous = point
            current = target
            continue
        if kind == "C":
            control_1 = (command[1], command[2])
            control_2 = (command[3], command[4])
            target = (command[5], command[6])
            estimated = (
                _distance(current, control_1)
                + _distance(control_1, control_2)
                + _distance(control_2, target)
            )
            steps = max(
                8,
                min(
                    _MAX_CURVE_SEGMENTS,
                    math.ceil(estimated / _MAX_SEGMENT_LENGTH),
                ),
            )
            previous = current
            for index in range(1, steps + 1):
                t = index / steps
                mt = 1.0 - t
                point = (
                    mt**3 * current[0]
                    + 3.0 * mt * mt * t * control_1[0]
                    + 3.0 * mt * t * t * control_2[0]
                    + t**3 * target[0],
                    mt**3 * current[1]
                    + 3.0 * mt * mt * t * control_1[1]
                    + 3.0 * mt * t * t * control_2[1]
                    + t**3 * target[1],
                )
                _append_segment(segments, previous, point)
                previous = point
            current = target
    return segments


def _curved_commands(start, end, curve_formula, geometry_scale):
    if curve_formula not in CONNECTION_CURVE_FORMULAS:
        curve_formula = DEFAULT_CONNECTION_CURVE_FORMULA
    dx = end[0] - start[0]
    dy = end[1] - start[1]

    if curve_formula == "arc":
        length = _distance(start, end)
        if length <= _EPSILON:
            return [("M", *start), ("L", *end)]
        normal_x, normal_y = _stable_normal(dx, dy, length)
        bow = min(80.0 * geometry_scale, length * 0.22)
        control = (
            (start[0] + end[0]) / 2.0 + normal_x * bow,
            (start[1] + end[1]) / 2.0 + normal_y * bow,
        )
        return [("M", *start), ("Q", *control, *end)]

    if curve_formula == "s_curve":
        length = _distance(start, end)
        if length <= _EPSILON:
            return [("M", *start), ("L", *end)]
        normal_x, normal_y = _stable_normal(dx, dy, length)
        bow = min(64.0 * geometry_scale, length * 0.18)
        control_1 = (
            start[0] + dx / 3.0 + normal_x * bow,
            start[1] + dy / 3.0 + normal_y * bow,
        )
        control_2 = (
            start[0] + dx * 2.0 / 3.0 - normal_x * bow,
            start[1] + dy * 2.0 / 3.0 - normal_y * bow,
        )
        return [
            ("M", *start),
            ("C", *control_1, *control_2, *end),
        ]

    if curve_formula == "adaptive" and abs(dy) > abs(dx):
        return [
            ("M", *start),
            (
                "C",
                start[0],
                start[1] + dy * 0.4,
                end[0],
                end[1] - dy * 0.4,
                *end,
            ),
        ]

    return [
        ("M", *start),
        (
            "C",
            start[0] + dx * 0.4,
            start[1],
            end[0] - dx * 0.4,
            end[1],
            *end,
        ),
    ]


def _route_points(style, start, end, geometry_scale):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    horizontal = abs(dx) >= abs(dy)

    if style == "orthogonal":
        if horizontal:
            middle = (start[0] + end[0]) / 2.0
            points = [start, (middle, start[1]), (middle, end[1]), end]
        else:
            middle = (start[1] + end[1]) / 2.0
            points = [start, (start[0], middle), (end[0], middle), end]
        return _compact_points(points)

    if horizontal:
        direction = 1.0 if dx >= 0.0 else -1.0
        lead = min(abs(dx) / 3.0, 48.0 * geometry_scale)
        points = [
            start,
            (start[0] + direction * lead, start[1]),
            (end[0] - direction * lead, end[1]),
            end,
        ]
    else:
        direction = 1.0 if dy >= 0.0 else -1.0
        lead = min(abs(dy) / 3.0, 48.0 * geometry_scale)
        points = [
            start,
            (start[0], start[1] + direction * lead),
            (end[0], end[1] - direction * lead),
            end,
        ]
    return _compact_points(points)


def _rounded_polyline_commands(points, corner_radius):
    if not points:
        return []
    if len(points) == 1:
        return [("M", *points[0])]

    radius = max(0.0, float(corner_radius))
    commands = [("M", *points[0])]
    for index in range(1, len(points) - 1):
        previous = points[index - 1]
        corner = points[index]
        following = points[index + 1]
        incoming = _distance(previous, corner)
        outgoing = _distance(corner, following)
        local_radius = min(float(radius), incoming / 2.0, outgoing / 2.0)
        if local_radius <= _EPSILON:
            commands.append(("L", *corner))
            continue
        entry = _point_toward(corner, previous, local_radius)
        exit_point = _point_toward(corner, following, local_radius)
        commands.append(("L", *entry))
        commands.append(("Q", *corner, *exit_point))
    commands.append(("L", *points[-1]))
    return commands


def _compact_points(points):
    compact = []
    for point in points:
        if not compact or _distance(compact[-1], point) > _EPSILON:
            compact.append(point)
    return compact


def _point_toward(origin, target, distance):
    length = _distance(origin, target)
    if length <= _EPSILON:
        return origin
    amount = distance / length
    return (
        origin[0] + (target[0] - origin[0]) * amount,
        origin[1] + (target[1] - origin[1]) * amount,
    )


def _stable_normal(dx, dy, length):
    normal_x = -dy / length
    normal_y = dx / length
    if normal_y < -_EPSILON or (
        abs(normal_y) <= _EPSILON and normal_x < 0.0
    ):
        normal_x = -normal_x
        normal_y = -normal_y
    return normal_x, normal_y


def _append_segment(segments, start, end):
    if _distance(start, end) > _EPSILON:
        segments.append((start[0], start[1], end[0], end[1]))


def _distance(first, second):
    return math.hypot(second[0] - first[0], second[1] - first[1])
