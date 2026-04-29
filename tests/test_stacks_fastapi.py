from demo_tools.stacks import fastapi as fastapi_stack


def test_fastapi_scaffold_writes_starter(tmp_path):
    meta = fastapi_stack.scaffold(tmp_path, "tmp-demo")
    assert (tmp_path / "app" / "main.py").exists()
    assert (tmp_path / "app" / "requirements.txt").exists()
    main_py = (tmp_path / "app" / "main.py").read_text()
    assert "FastAPI" in main_py
    assert meta["internal_port"] == 8000
    assert meta["stateful"] is True
