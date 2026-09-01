"""The html stack: plain files at the repo root, no toolchain."""
import json

from demo_tools.stacks import html as html_stack


def test_scaffold_reports_no_build_no_container(tmp_path):
    meta = html_stack.scaffold(tmp_path, "my-page")
    assert meta["stack"] == "html"
    assert meta["stateful"] is False


def test_writes_the_starter_files_at_the_repo_root(tmp_path):
    # Pages serves main at root for this stack, so index.html must be at the
    # top level — not under app/, which Pages cannot be pointed at.
    html_stack.scaffold(tmp_path, "my-page")
    for f in ("index.html", "app.js", "app.css"):
        assert (tmp_path / f).is_file(), f


def test_installs_no_toolchain(tmp_path):
    # The whole point of this stack: nothing that can rot.
    html_stack.scaffold(tmp_path, "my-page")
    for f in ("package.json", "package-lock.json", "Dockerfile", "vite.config.js"):
        assert not (tmp_path / f).exists(), f
    assert not (tmp_path / "node_modules").exists()


def test_is_installable_as_a_pwa(tmp_path):
    html_stack.scaffold(tmp_path, "my-page")
    assert (tmp_path / "manifest.webmanifest").is_file()
    assert (tmp_path / "sw.js").is_file()
    assert (tmp_path / "icon-192.png").is_file()
    assert (tmp_path / "icon-512.png").is_file()

    manifest = json.loads((tmp_path / "manifest.webmanifest").read_text())
    assert manifest["name"] == "my-page"


def test_manifest_is_path_independent(tmp_path):
    # Served both at a custom-domain root and at <user>.github.io/<repo>/. An
    # absolute scope claims the whole origin and the browser refuses to install.
    html_stack.scaffold(tmp_path, "my-page")
    manifest = json.loads((tmp_path / "manifest.webmanifest").read_text())
    assert not manifest["scope"].startswith("/")
    assert not manifest["start_url"].startswith("/")
    for icon in manifest["icons"]:
        assert not icon["src"].startswith("/"), icon["src"]


def test_head_tags_use_relative_asset_urls(tmp_path):
    html_stack.scaffold(tmp_path, "my-page")
    index = (tmp_path / "index.html").read_text()
    assert 'href="/manifest.webmanifest"' not in index
    assert 'href="/icon-192.png"' not in index


def test_page_has_a_favicon(tmp_path):
    html_stack.scaffold(tmp_path, "my-page")
    assert 'rel="icon"' in (tmp_path / "index.html").read_text()


def test_index_wires_up_the_manifest_and_worker(tmp_path):
    html_stack.scaffold(tmp_path, "my-page")
    index = (tmp_path / "index.html").read_text()
    assert "manifest.webmanifest" in index
    assert "serviceWorker" in index
    assert 'src="app.js"' in index or "app.js" in index
    assert "app.css" in index


def test_index_uses_relative_asset_paths(tmp_path):
    # Served from the repo root on a custom domain, but also from
    # user.github.io/<repo>/ before a domain is attached — absolute paths break
    # the second case.
    html_stack.scaffold(tmp_path, "my-page")
    index = (tmp_path / "index.html").read_text()
    assert 'href="/app.css"' not in index
    assert 'src="/app.js"' not in index


def test_names_the_demo_in_the_page(tmp_path):
    html_stack.scaffold(tmp_path, "chord-detector")
    assert "chord-detector" in (tmp_path / "index.html").read_text()


# --- --no-pwa ----------------------------------------------------------------

def test_no_pwa_omits_the_installable_shell(tmp_path):
    """A page whose job is to redirect has no use for an offline shell, and a
    worker in front of it can serve a stale copy of the very thing it bounces."""
    from demo_tools.stacks import html as html_stack

    html_stack.scaffold(tmp_path, "bouncer", pwa_assets=False)

    for name in ("sw.js", "manifest.webmanifest",
                 "icon-192.png", "icon-512.png", "icon-512-maskable.png"):
        assert not (tmp_path / name).exists(), name

    index = (tmp_path / "index.html").read_text()
    assert "serviceWorker" not in index
    assert "manifest" not in index


def test_pwa_is_still_the_default(tmp_path):
    from demo_tools.stacks import html as html_stack

    html_stack.scaffold(tmp_path, "installable")
    assert (tmp_path / "sw.js").is_file()
    assert "serviceWorker" in (tmp_path / "index.html").read_text()
