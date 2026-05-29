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
