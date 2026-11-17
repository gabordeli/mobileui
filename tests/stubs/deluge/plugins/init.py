class PluginInitBase:
    def __init__(self, plugin_name):
        self.plugin = self._plugin_cls(plugin_name)
