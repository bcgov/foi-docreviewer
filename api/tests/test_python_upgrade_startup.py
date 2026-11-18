"""Startup and operational commands using the real source tree."""

import os
from pathlib import Path
import subprocess
import sys
import pytest


def test_existing_probes_preserve_payloads(client):
    assert client.get("/api/healthz").json == {"message": "api is healthy"}
    assert client.get("/api/readyz").json == {"message": "api is ready"}


def test_migration_cli_exposes_commands():
    result = subprocess.run(
        [sys.executable, "manage.py", "db", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "upgrade" in result.stdout
    assert "heads" in result.stdout


def test_list_routes_retains_probe_routes():
    result = subprocess.run(
        [sys.executable, "manage.py", "list_routes"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "/api/healthz" in result.stdout


def test_actual_entrypoint_serves_and_terminates_cleanly(db, tmp_path):
    import signal
    import time
    import urllib.request

    env = dict(os.environ, FLASK_ENV="production")
    log = tmp_path / "server.log"
    with log.open("w") as output:
        process = subprocess.Popen(
            ["/bin/sh", "entrypoint.sh"],
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:5000/api/healthz", timeout=0.5
                    ) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if process.poll() is not None:
                        break
                    time.sleep(0.1)
            else:
                pytest.fail(log.read_text())
            assert process.poll() is None, log.read_text()
            process.terminate()
            process.wait(timeout=5)
            time.sleep(0.2)
            with pytest.raises(OSError):
                urllib.request.urlopen("http://127.0.0.1:5000/api/healthz", timeout=0.5)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)


def test_migration_failure_prevents_server(tmp_path):
    executable = tmp_path / "python"
    executable.write_text('#!/bin/sh\necho "$*" >> "$CALL_LOG"\nexit 7\n')
    executable.chmod(0o755)
    result = subprocess.run(
        ["/bin/sh", "entrypoint.sh"],
        env=dict(
            os.environ,
            PATH=str(tmp_path) + ":" + os.environ["PATH"],
            CALL_LOG=str(tmp_path / "calls"),
        ),
        timeout=5,
    )
    assert result.returncode == 7
    assert (tmp_path / "calls").read_text().splitlines() == ["manage.py db upgrade"]
