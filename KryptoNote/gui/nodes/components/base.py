class NodeComponent:
    def __init__(self):
        self.node = None
        
    def on_attached(self, node):
        self.node = node
        
    def on_event(self, event_type: str, *args, **kwargs):
        pass
