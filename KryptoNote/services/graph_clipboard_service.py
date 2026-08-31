from ..core.constants import fit_canvas_group_origin


class GraphClipboardService:
    """Manage deferred in-process graph copies for one database session."""

    DEFAULT_PASTE_OFFSET = (32.0, 32.0)

    def __init__(self, repo):
        self.repo = repo
        self._blueprint = None

    @staticmethod
    def _coerce_offset(
        offset=None,
        offset_y=None,
        offset_x=None,
    ):
        if (
            offset_x is None
            and offset_y is not None
            and isinstance(offset, (int, float))
        ):
            return float(offset), float(offset_y)
        if offset_x is not None or offset_y is not None:
            return (
                float(offset_x or 0),
                float(offset_y or 0),
            )
        if offset is None:
            return GraphClipboardService.DEFAULT_PASTE_OFFSET
        if isinstance(offset, dict):
            try:
                return float(offset.get("x", 0)), float(offset.get("y", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError("offset must contain numeric x and y") from exc
        if isinstance(offset, (int, float)):
            if offset_y is not None:
                return float(offset), float(offset_y)
            return float(offset), float(offset)
        try:
            x, y = offset
        except (TypeError, ValueError) as exc:
            raise ValueError("offset must be a number, pair or mapping") from exc
        return float(x), float(y)

    @classmethod
    def _target_origin(
        cls,
        blueprint,
        offset=None,
        offset_y=None,
        offset_x=None,
    ):
        if offset is None and offset_x is None and offset_y is None:
            origin = blueprint.get("origin") or {}
            return (
                float(origin.get("x", 0)) + cls.DEFAULT_PASTE_OFFSET[0],
                float(origin.get("y", 0)) + cls.DEFAULT_PASTE_OFFSET[1],
            )
        return cls._coerce_offset(offset, offset_y, offset_x)

    @staticmethod
    def _copy_summary(blueprint):
        node_ids = list(blueprint.get("node_ids") or [])
        source_ids = list(blueprint.get("source_ids") or [])
        selection_ids = list(blueprint.get("selection_ids") or source_ids)
        origin = dict(blueprint.get("origin") or {"x": 0.0, "y": 0.0})
        bounds = dict(blueprint.get("bounds") or {"width": 0.0, "height": 0.0})
        return {
            "source_ids": source_ids,
            "copied_ids": node_ids,
            "node_ids": node_ids,
            "selected_ids": selection_ids,
            "selection": selection_ids,
            "count": len(node_ids),
            "origin": origin,
            "bounds": bounds,
            "internal_connection_count": len(blueprint.get("connections") or []),
            "deferred": True,
        }

    @classmethod
    def _prepare_summary(cls, blueprint, offset_x, offset_y):
        relative_positions = [
            (
                float(node.get("relative_x", node.get("x", 0)) or 0),
                float(node.get("relative_y", node.get("y", 0)) or 0),
            )
            for node in blueprint.get("nodes") or ()
        ]
        offset_x, offset_y = fit_canvas_group_origin(
            offset_x,
            offset_y,
            relative_positions,
        )
        summary = cls._copy_summary(blueprint)
        summary.update(
            {
                "blueprint": blueprint,
                "target_origin": {
                    "x": float(offset_x),
                    "y": float(offset_y),
                },
                "offset": {
                    "x": float(offset_x),
                    "y": float(offset_y),
                },
                "offset_x": float(offset_x),
                "offset_y": float(offset_y),
                "payload_materialized": False,
            }
        )
        return summary

    def copy_graph(self, node_ids):
        blueprint = self.repo.build_graph_copy_blueprint(node_ids)
        self._blueprint = blueprint if blueprint.get("nodes") else None
        return self._copy_summary(blueprint)

    def prepare_paste(
        self,
        offset=None,
        offset_y=None,
        *,
        offset_x=None,
    ):
        """Prepare a lazy paste without reading or materialising payloads."""
        if not self.has_clipboard():
            raise ValueError("Clipboard is empty")
        dx, dy = self._target_origin(
            self._blueprint, offset, offset_y, offset_x
        )
        return self._prepare_summary(self._blueprint, dx, dy)

    def prepare_duplicate(
        self,
        node_ids,
        offset=None,
        offset_y=None,
        *,
        offset_x=None,
    ):
        """Build metadata and target origin for a deferred graph duplicate."""
        blueprint = self.repo.build_graph_copy_blueprint(node_ids)
        dx, dy = self._target_origin(blueprint, offset, offset_y, offset_x)
        return self._prepare_summary(blueprint, dx, dy)

    # Explicit graph-prefixed names make the prepare contract discoverable to
    # callers that also expose other paste/duplicate operations.
    prepare_graph_paste = prepare_paste
    prepare_graph_duplicate = prepare_duplicate

    def paste_graph(
        self,
        offset=None,
        offset_y=None,
        *,
        offset_x=None,
        progress_callback=None,
        cancel_check=None,
    ):
        preparation = self.prepare_paste(
            offset, offset_y, offset_x=offset_x
        )
        return self.repo.clone_graph(
            preparation["blueprint"],
            offset_x=preparation["offset_x"],
            offset_y=preparation["offset_y"],
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

    def duplicate_graph(
        self,
        node_ids,
        offset=None,
        offset_y=None,
        *,
        offset_x=None,
        progress_callback=None,
        cancel_check=None,
    ):
        preparation = self.prepare_duplicate(
            node_ids,
            offset,
            offset_y,
            offset_x=offset_x,
        )
        return self.repo.clone_graph(
            preparation["blueprint"],
            offset_x=preparation["offset_x"],
            offset_y=preparation["offset_y"],
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

    def clear_clipboard(self):
        self._blueprint = None

    def has_clipboard(self):
        return bool(self._blueprint and self._blueprint.get("nodes"))
