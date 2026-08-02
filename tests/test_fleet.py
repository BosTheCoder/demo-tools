import json
from unittest.mock import MagicMock, patch

import pytest

from demo_tools.fleet import (
    fetch_app_config,
    fly_app_name,
    is_always_on,
    list_apps,
    list_demos_only,
    parse_duration,
)


def test_list_apps_parses_fly_apps_list_output():
    fake_json = json.dumps([
        {"Name": "chord-detector", "Status": "deployed",
         "Organization": {"Slug": "personal"}},
        {"Name": "tolu-msg", "Status": "suspended",
         "Organization": {"Slug": "personal"}},
    ])
    with patch("demo_tools.fleet.subprocess.run") as run:
        run.return_value = MagicMock(stdout=fake_json, returncode=0)
        apps = list_apps()
    assert len(apps) == 2
    assert apps[0]["name"] == "chord-detector"
    assert apps[0]["status"] == "deployed"


def test_list_demos_only_drops_postgres_clusters():
    apps = [
        {"name": "demo1", "status": "deployed", "org": ""},
        {"name": "demo1-db", "status": "deployed", "org": ""},
    ]
    demos = list_demos_only(apps)
    assert [d["name"] for d in demos] == ["demo1"]


def test_list_demos_only_collapses_web_api_pair():
    apps = [
        {"name": "chord-web", "status": "deployed", "org": ""},
        {"name": "chord-api", "status": "deployed", "org": ""},
    ]
    demos = list_demos_only(apps)
    assert len(demos) == 1
    assert demos[0]["name"] == "chord"
    assert demos[0]["kind"] == "nextjs-fastapi"


def test_list_demos_only_keeps_lone_api_when_no_web():
    """An app named foo-api without a foo-web is treated as a regular demo."""
    apps = [
        {"name": "lonely-api", "status": "deployed", "org": ""},
    ]
    demos = list_demos_only(apps)
    assert len(demos) == 1
    assert demos[0]["name"] == "lonely-api"


def test_list_apps_reads_last_deployed_from_current_release():
    """`fly status --json` carries no App.CreatedAt, so age comes from here."""
    fake_json = json.dumps([
        {"Name": "demo1", "Status": "deployed", "Organization": {"Slug": "personal"},
         "CurrentRelease": {"CreatedAt": "2026-05-14T09:35:51Z"}},
    ])
    with patch("demo_tools.fleet.subprocess.run") as run:
        run.return_value = MagicMock(stdout=fake_json, returncode=0)
        apps = list_apps()
    assert apps[0]["last_deployed"] == "2026-05-14T09:35:51Z"


def test_list_apps_last_deployed_is_none_when_never_released():
    fake_json = json.dumps([
        {"Name": "demo1", "Status": "pending", "Organization": {"Slug": "personal"},
         "CurrentRelease": None},
        {"Name": "demo2", "Status": "pending", "Organization": {"Slug": "personal"},
         "CurrentRelease": {"CreatedAt": "0001-01-01T00:00:00Z"}},
    ])
    with patch("demo_tools.fleet.subprocess.run") as run:
        run.return_value = MagicMock(stdout=fake_json, returncode=0)
        apps = list_apps()
    assert apps[0]["last_deployed"] is None
    assert apps[1]["last_deployed"] is None


def test_fly_app_name_expands_nextjs_fastapi_to_the_web_app():
    """The collapsed <base> name is synthetic; Fly only knows <base>-web."""
    demo = {"name": "chord", "kind": "nextjs-fastapi"}
    assert fly_app_name(demo) == "chord-web"


def test_fly_app_name_passes_through_ordinary_demos():
    assert fly_app_name({"name": "chord", "kind": "nextjs"}) == "chord"
    assert fly_app_name({"name": "chord"}) == "chord"


def test_fetch_app_config_returns_none_when_fly_fails():
    import subprocess as sp
    with patch("demo_tools.fleet.subprocess.run",
               side_effect=sp.CalledProcessError(1, "fly")):
        assert fetch_app_config("nope") is None


def test_fetch_app_config_returns_none_on_garbage_output():
    with patch("demo_tools.fleet.subprocess.run") as run:
        run.return_value = MagicMock(stdout="not json", returncode=0)
        assert fetch_app_config("nope") is None


def test_fetch_app_config_parses_json():
    with patch("demo_tools.fleet.subprocess.run") as run:
        run.return_value = MagicMock(
            stdout='{"http_service":{"min_machines_running":1}}', returncode=0
        )
        assert fetch_app_config("x") == {"http_service": {"min_machines_running": 1}}


def test_is_always_on_for_service_profile():
    """A `service`-profile app: auto_stop off and a machine pinned running."""
    config = {"http_service": {"auto_stop_machines": False, "min_machines_running": 1}}
    assert is_always_on(config) is True


def test_is_not_always_on_for_demo_profile():
    config = {"http_service": {"auto_stop_machines": "stop", "min_machines_running": 0}}
    assert is_always_on(config) is False


def test_suspend_is_not_always_on():
    config = {"http_service": {"auto_stop_machines": "suspend", "min_machines_running": 0}}
    assert is_always_on(config) is False


def test_missing_auto_stop_counts_as_always_on():
    """Fly's default when the key is absent is "off" — it never stops."""
    config = {"services": [{"internal_port": 8000, "protocol": "tcp"}]}
    assert is_always_on(config) is True


def test_services_block_with_autostop_is_not_always_on():
    config = {"services": [{"internal_port": 8000, "auto_stop_machines": "stop",
                            "min_machines_running": 0}]}
    assert is_always_on(config) is False


def test_unreadable_config_is_treated_as_always_on():
    """Fail safe: never destroy an app we could not classify."""
    assert is_always_on(None) is True


def test_config_without_services_is_treated_as_always_on():
    assert is_always_on({}) is True


def test_any_always_on_block_protects_the_whole_app():
    config = {
        "http_service": {"auto_stop_machines": "stop", "min_machines_running": 0},
        "services": [{"internal_port": 8000, "min_machines_running": 2}],
    }
    assert is_always_on(config) is True


def test_parse_days():
    assert parse_duration("14d").total_seconds() == 14 * 86400


def test_parse_hours():
    assert parse_duration("2h").total_seconds() == 2 * 3600


def test_parse_minutes():
    assert parse_duration("30m").total_seconds() == 30 * 60


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        parse_duration("forever")
