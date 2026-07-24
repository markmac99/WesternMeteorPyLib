""" Regression tests for optional REBOUND dependency reporting. """

import builtins
import contextlib
import importlib.util
import io
import os
import runpy
import types

import pytest


REBOUND_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "REBOUND.py")


def _mockReboundImports(monkeypatch, reboundx_found):
    """ Mock the optional REBOUND imports without changing the installed environment. """

    real_import = builtins.__import__
    rebound = types.ModuleType("rebound")
    reboundx = types.ModuleType("reboundx")
    reboundx.constants = types.SimpleNamespace()

    def mockedImport(name, globals=None, locals=None, fromlist=(), level=0):

        if name == "rebound":
            return rebound

        if (name == "reboundx") or name.startswith("reboundx."):
            if not reboundx_found:
                raise ImportError("No module named 'reboundx'")

            return reboundx

        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", mockedImport)


def _loadReboundModule():
    """ Load REBOUND.py under an isolated module name and capture its import-time output. """

    spec = importlib.util.spec_from_file_location("_wmpl_test_rebound", REBOUND_PATH)
    module = importlib.util.module_from_spec(spec)
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        spec.loader.exec_module(module)

    return module, stdout.getvalue()


def testMissingReboundxIsSilentUntilUsed(monkeypatch):
    """ A missing optional dependency must not produce output during an unrelated import. """

    _mockReboundImports(monkeypatch, reboundx_found=False)
    module, import_output = _loadReboundModule()

    assert import_output == ""
    assert not module.REBOUND_FOUND
    assert module._REBOUND_IMPORT_ERROR == "No module named 'reboundx'"

    for function, args in [
            (module.convertToBarycentric, ([], 0)),
            (module.reboundSimulate, (None, None))]:

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = function(*args)

        assert result is None
        assert "packages are required" in stdout.getvalue()
        assert "The error was: No module named 'reboundx'" in stdout.getvalue()


def testMissingReboundxCommandLineError(monkeypatch):
    """ Direct command-line use must report the cause, guidance, and a failing exit status. """

    _mockReboundImports(monkeypatch, reboundx_found=False)
    stdout = io.StringIO()

    with pytest.raises(SystemExit) as exc_info:
        with contextlib.redirect_stdout(stdout):
            runpy.run_path(REBOUND_PATH, run_name="__main__")

    assert exc_info.value.code == 1
    assert "The error was: No module named 'reboundx'" in stdout.getvalue()
    assert "pip install rebound reboundx" in stdout.getvalue()
    assert "Windows Subsystem for Linux" in stdout.getvalue()


def testAvailableReboundDependenciesAreSilent(monkeypatch):
    """ Successful optional imports must preserve the normal REBOUND execution path. """

    _mockReboundImports(monkeypatch, reboundx_found=True)
    module, import_output = _loadReboundModule()

    assert import_output == ""
    assert module.REBOUND_FOUND
    assert module._REBOUND_IMPORT_ERROR is None
