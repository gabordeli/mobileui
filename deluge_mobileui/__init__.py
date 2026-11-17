"""Deluge MobileUi core plugin."""

from deluge.plugins.init import PluginInitBase

from .version import __version__

__all__ = ["CorePlugin", "__version__"]


class CorePlugin(PluginInitBase):
    def __init__(self, plugin_name):
        from .core import Core as _plugin_cls

        self._plugin_cls = _plugin_cls
        super().__init__(plugin_name)
