import subprocess

from demo_tools.scaffold import scaffold_demo


def test_scaffold_bare_creates_full_demo(tmp_path):
    target = tmp_path / "tmp-demo"
    scaffold_demo("bare", "tmp-demo", target)
    assert (target / "app" / ".gitkeep").exists()
    assert (target / "Dockerfile").exists()
    assert (target / "fly.toml").exists()
    assert (target / "compose.yml").exists()
    assert (target / "justfile").exists()
    assert (target / "infra" / "fly" / "deploy.sh").exists()
    assert (target / ".demo-template-version").exists()


def test_scaffold_bare_initializes_git(tmp_path):
    target = tmp_path / "tmp-demo"
    scaffold_demo("bare", "tmp-demo", target)
    assert (target / ".git").is_dir()
    log = subprocess.run(
        ["git", "-C", str(target), "log", "--oneline"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "initial scaffold" in log.lower()
