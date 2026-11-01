# QianXun runtime: make Qt find its plugins when the install path contains characters outside the
# system ANSI code page (e.g. Chinese folder names on an English-locale Windows). Qt 5 derives the
# default plugin path through ANSI APIs, which turns such characters into '?'. We set the library
# path explicitly (from a Python unicode string) as soon as PyQt5.QtCore is imported.
import sys
if sys.platform == "win32":
    import os

    class _Loader:
        def __init__(self, inner):
            self._inner = inner

        def create_module(self, spec):
            return self._inner.create_module(spec)

        def exec_module(self, module):
            self._inner.exec_module(module)
            try:
                d = os.path.join(os.path.dirname(os.path.abspath(module.__file__)), "Qt5", "plugins")
                if os.path.isdir(d):
                    module.QCoreApplication.setLibraryPaths([d])
            except Exception:
                pass

    class _Finder:
        def find_spec(self, name, path, target=None):
            if name != "PyQt5.QtCore":
                return None
            sys.meta_path.remove(self)
            try:
                import importlib.machinery
                spec = importlib.machinery.PathFinder.find_spec(name, path)
            finally:
                pass
            if spec is not None and spec.loader is not None:
                spec.loader = _Loader(spec.loader)
            return spec

    sys.meta_path.insert(0, _Finder())
