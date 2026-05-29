import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "demo_tools", *args],
        capture_output=True,
        text=True,
    )


def test_main_routes_demo_help():
    r = _run("demo", "--help")
    assert r.returncode == 0, r.stderr
    assert "prune" in r.stdout


def test_main_routes_init_help():
    r = _run("init", "--help")
    assert r.returncode == 0, r.stderr
    assert "adopt" in r.stdout


def test_main_no_args_errors():
    r = _run()
    assert r.returncode != 0
