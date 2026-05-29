from demo_tools._reflect import build_argv, reflect_tools


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


def test_build_argv_scaffold_positionals_then_option():
    spec = _by_name()["demo_init.scaffold"]
    argv = build_argv(spec, {"stack": "nextjs", "name": "foo", "profile": "service"})
    assert argv[1:] == [
        "-m", "demo_tools", "init", "scaffold",
        "nextjs", "foo", "--profile", "service",
    ]


def test_build_argv_omits_false_flag():
    spec = _by_name()["demo.prune"]
    argv = build_argv(spec, {"dry_run": False})
    assert "--dry-run" not in argv


def test_build_argv_includes_true_flag():
    spec = _by_name()["demo.prune"]
    argv = build_argv(spec, {"dry_run": True})
    assert "--dry-run" in argv


def test_build_argv_skips_none_value_option():
    spec = _by_name()["demo.prune"]
    argv = build_argv(spec, {"older_than": None, "dry_run": True})
    assert "--older-than" not in argv
    assert "None" not in argv
    assert "--dry-run" in argv


def test_build_argv_skips_none_positional():
    spec = _by_name()["demo_init.scaffold"]
    argv = build_argv(spec, {"stack": "nextjs", "name": None})
    assert "None" not in argv
    assert "nextjs" in argv
