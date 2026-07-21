class GraphCommandService:
    """Application-level graph commands shared by the QML adapter."""

    def __init__(self, node_model, connection_model, node_service):
        self._node_model = node_model
        self._conn_model = connection_model
        self._node_service = node_service
        self._link_start_id = None
        self._pending_commits = False

    def delete_node_after_animation(
        self,
        node_id,
        on_start_vacuum=None,
        on_finish_vacuum=None,
        on_waiting_lock=None,
        on_success=None,
        on_error=None,
    ):
        return self._node_service.delete_node_cascade(
            node_id,
            on_start_vacuum=on_start_vacuum,
            on_finish_vacuum=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            on_success=on_success,
            on_error=on_error,
        )

    def delete_nodes_after_animation(
        self,
        node_ids,
        on_start_vacuum=None,
        on_finish_vacuum=None,
        on_waiting_lock=None,
        on_success=None,
        on_error=None,
    ):
        node_ids = list(dict.fromkeys(node_ids))
        if not node_ids:
            if on_success:
                on_success()
            if on_finish_vacuum:
                on_finish_vacuum()
            return None

        return self._node_service.delete_nodes_cascade(
            node_ids,
            on_start_vacuum=on_start_vacuum,
            on_finish_vacuum=on_finish_vacuum,
            on_waiting_lock=on_waiting_lock,
            on_success=on_success,
            on_error=on_error,
        )

    def handle_link_click(self, node_id):
        if self._link_start_id is None:
            self._link_start_id = node_id
            self._node_model.set_selected(node_id, True)
            return "LINKING: Chain started. Click next...", "secure"

        if self._link_start_id != node_id:
            if not self._conn_model.connection_exists(self._link_start_id, node_id):
                conn_id = self._node_service.add_connection(
                    self._link_start_id, node_id, commit=False
                )
                self._conn_model.add_connection(conn_id, self._link_start_id, node_id)
                self._pending_commits = True
                status = ("LINKED! Chain moves to new node.", "secure")
            else:
                status = None

            self._node_model.set_selected(self._link_start_id, False)
            self._link_start_id = node_id
            self._node_model.set_selected(node_id, True)
            return status

        return None

    def delete_connection(self, conn_id):
        return self._conn_model.set_deleting(conn_id, True, finalize=True)

    def delete_connection_after_animation(self, conn_id):
        self._node_service.delete_connection(conn_id)
        self._conn_model.remove_connection(conn_id)

    def toggle_link_mode_off(self):
        if self._link_start_id is not None:
            self._node_model.set_selected(self._link_start_id, False)
            self._link_start_id = None
        self.commit_pending()

    def commit_pending(self):
        if self._pending_commits:
            self._node_service.commit_changes()
            self._pending_commits = False
