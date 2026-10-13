"""Checked, recoverable Windows source setup; no device or Git operations."""

import argparse
import json
import os
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class SetupFailure(RuntimeError):
    pass


class Setup:
    def __init__(self, root):
        self.root = root.resolve()
        self.step = "Check project"
        self.advice = "Extract the complete project and run its Setup-BnKG-After-Move.cmd."
        self.log = None
        self.backup = None

    def say(self, text):
        print(text, flush=True)
        if self.log:
            with self.log.open("a", encoding="utf-8") as handle:
                handle.write(text + "\n")

    def run(self, args, timeout=120, env=None):
        # File output avoids pipe deadlocks, retains diagnostics and supports timeout.
        output = self.log.with_suffix(".command.txt")
        with output.open("w", encoding="utf-8") as handle:
            try:
                result = subprocess.run(
                    args,
                    cwd=self.root,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    env=env,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise SetupFailure(
                    f"Command timed out after {timeout} seconds. See {output}"
                ) from exc
        detail = output.read_text(encoding="utf-8", errors="replace")
        if detail.strip():
            self.say(detail.rstrip())
        if result.returncode:
            raise SetupFailure(f"Command exited with code {result.returncode}. See output above.")

    def perform(self, *, check_only=False, no_launch=False):
        try:
            if (
                os.name != "nt"
                or not ((3, 12) <= sys.version_info[:2] < (3, 15))
                or struct.calcsize("P") != 8
            ):
                raise SetupFailure("This helper requires Windows and 64-bit Python 3.12–3.14.")
            for relative in ("BnKG_Run_Python.py", "requirements.lock", "src/bnkg/app.py"):
                if not (self.root / relative).is_file():
                    raise SetupFailure(f"Missing required project file: {relative}")
            self.say(f"[PASS 1/6] Project folder: {self.root}")
            if check_only:
                self.say(
                    "CHECK ONLY complete. No environment changes, installation or app launch performed."
                )
                return 0
            run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
            logs = self.root / ".cache" / "setup" / run_id
            logs.mkdir(parents=True)
            self.log = logs / "setup.log"
            self.say(f"Setup log: {self.log}")
            self.step = "Preserve previous environment"
            self.advice = "Close the app, terminals and editors using .venv, then rerun setup. Never delete your only backup."
            environment = self.root / ".venv"
            if environment.exists() or environment.is_symlink():
                if environment.is_symlink() or environment.is_junction():
                    raise SetupFailure(
                        "The .venv is a link/junction; review its target manually before setup."
                    )
                self.backup = self.root / (".venv-before-move-" + run_id)
                if not environment.resolve().is_relative_to(
                    self.root
                ) or not self.backup.resolve().is_relative_to(self.root):
                    raise SetupFailure("Environment backup path is outside this project.")
                environment.rename(self.backup)
                if environment.exists() or not self.backup.is_dir():
                    raise SetupFailure("Could not verify the environment backup.")
                self.say(f"Old environment preserved: {self.backup}")
            self.say("[PASS 2/6] Existing environment preserved, or none was present.")
            self.step = "Create Python environment"
            self.advice = "Check free disk space and folder write access; repair/install Python with venv and pip, then rerun."
            self.run([sys.executable, "-m", "venv", str(environment)])
            python = environment / "Scripts" / "python.exe"
            if not python.is_file():
                raise SetupFailure("venv reported success but its Python executable is missing.")
            self.run(
                [
                    str(python),
                    "-c",
                    "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve()==pathlib.Path(sys.argv[1]).resolve(); print(sys.version)",
                    str(environment),
                ]
            )
            self.say("[PASS 3/6] New environment created and its location verified.")
            self.step = "Install dependencies"
            self.advice = "Check internet/proxy access, disk space and the pip error. Keep hash verification enabled; rerun after correcting the cause."
            self.say(
                "Installing pinned dependencies. This can take several minutes; please leave this window open."
            )
            self.run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--require-hashes",
                    "-r",
                    str(self.root / "requirements.lock"),
                ],
                timeout=900,
            )
            self.run([str(python), "-m", "pip", "check"])
            self.say("[PASS 4/6] Dependency installation and consistency check passed.")
            self.step = "Verify app startup and clean shutdown"
            self.advice = "Read the setup log. Check Qt/dependency errors and use supported 64-bit Python; share the failed step and log if unresolved."
            launcher = str(self.root / "BnKG_Run_Python.py")
            self.run([str(python), launcher, "--version"])
            smoke_dir = logs / "startup-check"
            smoke_env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            self.run(
                [str(python), launcher, "--smoke-test", "--data-dir", str(smoke_dir)],
                timeout=45,
                env=smoke_env,
            )
            result = json.loads((smoke_dir / "smoke-result.json").read_text(encoding="utf-8"))
            if result.get("logging") is not False or result.get("source") != "disconnected":
                raise SetupFailure("Startup check did not report disconnected, logging-off state.")
            self.say(
                "[PASS 5/6] App startup/shutdown checked with isolated test data; no SLM connected."
            )
            self.step = "Launch app"
            self.advice = "Run Launch-BnKG.cmd for visible error output; check the setup log and confirm the window opens."
            if no_launch:
                self.say("[SKIP 6/6] App launch omitted by --no-launch. Setup checks passed.")
            else:
                pythonw = environment / "Scripts" / "pythonw.exe"
                with (logs / "app-launch.log").open("w", encoding="utf-8") as handle:
                    process = subprocess.Popen(
                        [str(pythonw), launcher],
                        cwd=self.root,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                    )
                time.sleep(3)
                if process.poll() is not None:
                    raise SetupFailure("The app exited during launch; inspect app-launch.log.")
                self.say(
                    "[PASS 6/6] App process is running. Confirm its window is visible; setup cannot verify your visual interaction."
                )
            self.say("SETUP COMPLETE. B&KG = BnKG.")
            self.say(f"MANUAL NEXT STEP: Open Codex and add/open this project folder: {self.root}")
            self.say(
                "Start a task there: Read AGENTS.md, 00_START_HERE.md and 01_PROGRESS.md; reconcile Git status and resume."
            )
            self.say(
                "The old Codex task may keep its old directory. Setup does not move or reconfigure an active Codex task."
            )
            self.say(
                "Next time, double-click Launch-BnKG.cmd. Keep the environment backup until satisfied."
            )
            return 0
        except (OSError, ValueError, SetupFailure) as exc:
            self.say(f"[FAILED: {self.step}] {exc}")
            self.say("WHAT TO DO: " + self.advice)
            if self.backup:
                self.say(f"Previous environment remains at: {self.backup}")
            self.say(
                "STOPPED. Later steps were not run. Correct the cause and rerun Setup-BnKG-After-Move.cmd."
            )
            return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    return Setup(Path(__file__).resolve().parents[1]).perform(
        check_only=args.check_only, no_launch=args.no_launch
    )


if __name__ == "__main__":
    raise SystemExit(main())
