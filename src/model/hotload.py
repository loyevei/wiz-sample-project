import os
import time


class Hotload:
    def _project_root(self):
        fs = wiz.project.fs()
        return fs.abspath()

    def _resolve_path(self, relative_path):
        project_root = self._project_root()
        candidates = [
            os.path.join(project_root, "bundle", "src", relative_path),
            os.path.join(project_root, "build", "src", relative_path),
            os.path.join(project_root, "src", relative_path),
        ]

        resolved = next((path for path in candidates if os.path.isfile(path)), None)
        if resolved is None:
            raise FileNotFoundError(f"{relative_path} not found in bundle/src, build/src, or src")
        return resolved

    def load_scope(self, relative_path, name_prefix="wiz_hot_module"):
        module_path = self._resolve_path(relative_path)

        with open(module_path, "r", encoding="utf-8") as f:
            code = f.read()

        scope = {
            "__name__": f"{name_prefix}_{int(time.time() * 1000)}",
            "wiz": wiz,
            "season": __import__("season"),
        }
        exec(compile(code, module_path, "exec"), scope, scope)
        return scope

    def load_symbol(self, relative_path, symbol_name, name_prefix="wiz_hot_module"):
        scope = self.load_scope(relative_path, name_prefix=name_prefix)
        symbol = scope.get(symbol_name)
        if symbol is None:
            raise RuntimeError(f"{symbol_name} not found after exec: {relative_path}")
        return symbol


Model = Hotload()