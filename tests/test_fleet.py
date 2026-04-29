import json
from unittest.mock import MagicMock, patch

import pytest

from demo_tools.fleet import list_apps, list_demos_only, parse_duration


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


def test_parse_days():
    assert parse_duration("14d").total_seconds() == 14 * 86400


def test_parse_hours():
    assert parse_duration("2h").total_seconds() == 2 * 3600


def test_parse_minutes():
    assert parse_duration("30m").total_seconds() == 30 * 60


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        parse_duration("forever")
