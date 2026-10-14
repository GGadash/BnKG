import importlib.util
import sys
from pathlib import Path

import pytest


def helper():
    spec = importlib.util.spec_from_file_location(
        "setup_after_move", Path(__file__).parents[1] / "scripts/setup_after_move.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def project(root):
    for name in ("BnKG_Run_Python.py", "requirements.lock", "src/bnkg/app.py"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows setup helper")
def test_failed_venv_keeps_backup_stops_later_steps(tmp_path, monkeypatch, capsys):
    module = helper()
    project(tmp_path)
    old = tmp_path / ".venv"
    old.mkdir()
    (old / "sentinel").write_text("preserve")
    setup = module.Setup(tmp_path)
    commands = []

    def fail(args, **kwargs):
        commands.append(args)
        raise OSError("simulated venv failure")

    monkeypatch.setattr(setup, "run", fail)
    assert setup.perform(no_launch=True) == 1
    assert len(commands) == 1
    assert (setup.backup / "sentinel").read_text() == "preserve"
    output = capsys.readouterr().out
    assert "FAILED: Create Python environment" in output
    assert "WHAT TO DO:" in output and "Later steps were not run" in output


def test_command_error_and_timeout_are_failures(tmp_path):
    module = helper()
    setup = module.Setup(tmp_path)
    setup.log = tmp_path / "setup.log"
    import pytest

    with pytest.raises(module.SetupFailure, match="code 7"):
        setup.run([sys.executable, "-c", "raise SystemExit(7)"])
    with pytest.raises(module.SetupFailure, match="timed out"):
        setup.run([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.1)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows setup helper")
def test_missing_project_is_not_mutated(tmp_path, capsys):
    setup = helper().Setup(tmp_path)
    assert setup.perform() == 1
    assert not list(tmp_path.iterdir())
    assert "Missing required project file" in capsys.readouterr().out
