from demo_tools.stacks import streamlit as streamlit_stack


def test_streamlit_scaffold_writes_starter(tmp_path):
    meta = streamlit_stack.scaffold(tmp_path, "tmp-demo")
    assert (tmp_path / "app" / "streamlit_app.py").exists()
    assert (tmp_path / "app" / "requirements.txt").exists()
    assert meta["internal_port"] == 8501
    assert meta["stateful"] is True
