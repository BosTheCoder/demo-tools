import pytest

from demo_tools.adopt import overlay_infra


def test_adopt_overlay_skips_existing_dockerfile(tmp_path):
    # Pretend this is an existing dockerized repo
    (tmp_path / "Dockerfile").write_text("FROM custom-base\n# original\n")
    (tmp_path / "package.json").write_text('{"dependencies":{"next":"14"}}')

    overlay_infra(tmp_path, name="my-existing", stack="nextjs",
                  stateful=False, internal_port=3000)

    # Original Dockerfile preserved
    assert "FROM custom-base" in (tmp_path / "Dockerfile").read_text()
    # Original package.json preserved
    assert "next" in (tmp_path / "package.json").read_text()
    # Infra files added
    assert (tmp_path / "justfile").exists()
    assert (tmp_path / "fly.toml").exists()
    assert (tmp_path / "infra" / "fly" / "deploy.sh").exists()
    assert (tmp_path / ".demo-template-version").exists()


def test_adopt_overlay_refuses_without_dockerfile(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies":{"next":"14"}}')
    with pytest.raises(FileNotFoundError):
        overlay_infra(tmp_path, name="x", stack="nextjs",
                      stateful=False, internal_port=3000)


def test_adopt_overlay_writes_demo_template_version(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM alpine\n")
    overlay_infra(tmp_path, name="x", stack="bare",
                  stateful=False, internal_port=3000)
    answers = (tmp_path / ".demo-template-version").read_text()
    assert "stack: bare" in answers
    assert "name: x" in answers


def test_adopt_overlay_passes_profile_to_template(tmp_path):
    """overlay_infra(profile='service') renders service-mode fly.toml.

    Note: in adopt mode, fly.toml is normally protected by skip_if_exists, so
    the rendered fly.toml only lands when there's no existing one. This test
    sets up that case (Dockerfile present, no fly.toml) — which matches the
    fresh-adopt scenario for a repo that previously had no Fly config.
    """
    (tmp_path / "Dockerfile").write_text("FROM alpine\n")

    overlay_infra(tmp_path, name="svc", stack="bare",
                  stateful=False, internal_port=3000, profile="service")

    fly_toml = (tmp_path / "fly.toml").read_text()
    assert 'auto_stop_machines = "off"' in fly_toml
    assert "min_machines_running = 1" in fly_toml


def test_adopt_overlay_writes_profile_into_answers(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM alpine\n")
    overlay_infra(tmp_path, name="svc", stack="bare",
                  stateful=False, internal_port=3000, profile="service")
    answers = (tmp_path / ".demo-template-version").read_text()
    assert "profile: service" in answers


def test_adopt_overlay_default_profile_is_demo(tmp_path):
    """Omitting profile defaults to demo — backward-compat for existing callers."""
    (tmp_path / "Dockerfile").write_text("FROM alpine\n")
    overlay_infra(tmp_path, name="x", stack="bare",
                  stateful=False, internal_port=3000)  # no profile kwarg
    answers = (tmp_path / ".demo-template-version").read_text()
    assert "profile: demo" in answers
