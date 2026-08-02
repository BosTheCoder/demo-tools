from unittest.mock import patch, MagicMock

from demo_tools.stacks import vite as vite_stack


def test_vite_scaffold_invokes_npm_create_vite(tmp_path):
    with patch("demo_tools.stacks.vite.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        meta = vite_stack.scaffold(tmp_path, "tmp-demo")
        # We expect at least one call (the create-vite scaffolding); the actual
        # implementation may also run `npm install` afterwards.
        assert run.call_count >= 1
        first_cmd = run.call_args_list[0].args[0]
        joined = " ".join(first_cmd)
        assert "create vite" in joined or "create-vite" in joined
        assert "react-ts" in joined
    assert meta["internal_port"] == 80
    assert meta["stateful"] is False
