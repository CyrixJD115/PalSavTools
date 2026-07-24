"""
In-memory Python module loader, registered on sys.meta_path.

Register via:  register(modules={"name.py": b"<source bytes>"})

- Pure-Python modules are served straight from the passed bytes dict; the
  original .py never touches disk.
- C extensions (.so/.pyd/.dylib) are NOT supported here on purpose — the
  platform dynamic linker needs real files (see POC README). Keep native wheels
  as real bundled resources.
"""

import importlib.abc
import importlib.machinery
import importlib.util
import sys


class _InMemoryLoader(importlib.abc.Loader):
    def __init__(self, name, source):
        self._name = name
        self._source = source

    def create_module(self, spec):
        return None  # default module creation

    def exec_module(self, module):
        exec(compile(self._source, f"<embedded:{self._name}>", "exec"), module.__dict__)


class _InMemoryFinder(importlib.abc.MetaPathFinder):
    def __init__(self, modules):
        # modules: dict[str, bytes]  (key = fully-qualified module name)
        self._modules = modules

    def find_spec(self, fullname, path=None, target=None):
        src = self._modules.get(fullname)
        if src is None:
            return None
        loader = _InMemoryLoader(fullname, src)
        return importlib.util.spec_from_loader(fullname, loader, origin="embedded")


def register(modules):
    """Install the finder at the front of sys.meta_path. Idempotent."""
    for f in list(sys.meta_path):
        if isinstance(f, _InMemoryFinder):
            sys.meta_path.remove(f)
    sys.meta_path.insert(0, _InMemoryFinder(modules))
