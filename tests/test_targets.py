"""Deploy-target rules: which stacks a target accepts, and how each publishes."""
import pytest

from demo_tools.targets import (
    VALID_TARGETS,
    check_target_stack,
    publish_mode,
    targets_for_stack,
)


def test_pages_is_a_valid_target():
    assert set(VALID_TARGETS) == {"fly", "local", "pages"}


@pytest.mark.parametrize("stack", ["html", "vite", "bare"])
def test_pages_accepts_static_capable_stacks(stack):
    check_target_stack("pages", stack)  # does not raise


@pytest.mark.parametrize("stack", ["fastapi", "streamlit", "nextjs-fastapi"])
def test_pages_rejects_server_backed_stacks(stack):
    with pytest.raises(ValueError) as exc:
        check_target_stack("pages", stack)
    msg = str(exc.value)
    assert stack in msg
    assert "server" in msg.lower()
    # The error has to point somewhere useful, not just say no.
    assert "--target fly" in msg


def test_pages_rejects_nextjs_and_says_why():
    with pytest.raises(ValueError) as exc:
        check_target_stack("pages", "nextjs")
    assert "export" in str(exc.value).lower()


@pytest.mark.parametrize("target", ["fly", "local"])
def test_html_is_pages_only(target):
    # html has no Dockerfile, and both fly and local build an image.
    with pytest.raises(ValueError) as exc:
        check_target_stack(target, "html")
    assert "Dockerfile" in str(exc.value)
    assert "--target pages" in str(exc.value)


@pytest.mark.parametrize("stack", ["nextjs", "fastapi", "streamlit", "vite", "bare"])
@pytest.mark.parametrize("target", ["fly", "local"])
def test_fly_and_local_accept_every_dockerised_stack(target, stack):
    check_target_stack(target, stack)  # does not raise


def test_unknown_target_is_rejected():
    with pytest.raises(ValueError) as exc:
        check_target_stack("heroku", "vite")
    assert "heroku" in str(exc.value)


def test_publish_mode_serves_repo_root_for_no_build_stacks():
    # Nothing is built, so the repo root IS the site — no gh-pages branch.
    assert publish_mode("html") == "root"


def test_publish_mode_uses_a_branch_for_build_stacks():
    # dist/ can't live at the repo root, so it goes to gh-pages.
    assert publish_mode("vite") == "branch"


def test_publish_mode_defaults_bare_to_branch():
    # bare brings its own output dir; a branch is the safe assumption.
    assert publish_mode("bare") == "branch"


def test_targets_for_stack_lists_only_usable_targets():
    assert targets_for_stack("html") == ("pages",)
    assert targets_for_stack("vite") == ("fly", "local", "pages")
    assert targets_for_stack("fastapi") == ("fly", "local")
