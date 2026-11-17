import json
import os
import tempfile


class Config(dict):
    def __init__(self, filename, defaults=None, config_dir=None):
        super().__init__(defaults or {})
        if os.path.isabs(filename):
            self.config_file = filename
        else:
            base = config_dir or tempfile.gettempdir()
            self.config_file = os.path.join(base, filename)

    def save(self):
        with open(self.config_file, "w", encoding="utf-8") as handle:
            json.dump(dict(self), handle, indent=2)
        os.chmod(self.config_file, 0o600)
