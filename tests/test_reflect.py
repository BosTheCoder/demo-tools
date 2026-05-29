from demo_tools._reflect import reflect_tools


def _by_name():
    return {t["name"]: t for t in reflect_tools()}


def test_reflect_includes_all_current_commands():
    names = set(_by_name())
    assert {
        "demo_init.scaffold",
        "demo_init.adopt",
        "demo.list",
        "demo.prune",
    } <= names


def test_scaffold_requires_stack_and_name():
    schema = _by_name()["demo_init.scaffold"]["input_schema"]
    assert set(schema["required"]) == {"stack", "name"}
    assert schema["properties"]["stack"]["type"] == "string"


def test_prune_marked_destructive_list_is_not():
    tools = _by_name()
    assert tools["demo.prune"]["destructive"] is True
    assert tools["demo.list"]["destructive"] is False


def test_prune_params_classify_options_and_flags():
    params = {p["name"]: p for p in _by_name()["demo.prune"]["params"]}
    assert params["older_than"]["kind"] == "option"
    assert params["older_than"]["opt"] == "--older-than"
    assert params["older_than"]["is_flag"] is False
    assert params["dry_run"]["kind"] == "option"
    assert params["dry_run"]["opt"] == "--dry-run"
    assert params["dry_run"]["is_flag"] is True
    assert params["yes"]["is_flag"] is True


def test_scaffold_params_positionals_vs_option():
    params = {p["name"]: p for p in _by_name()["demo_init.scaffold"]["params"]}
    assert params["stack"]["kind"] == "argument"
    assert params["name"]["kind"] == "argument"
    assert params["profile"]["kind"] == "option"
    assert params["profile"]["opt"] == "--profile"


def test_option_help_becomes_description():
    schema = _by_name()["demo.prune"]["input_schema"]
    assert "description" in schema["properties"]["dry_run"]
