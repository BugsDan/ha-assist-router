"""Repository checks; sole approved runtime delta is legacy URL cleanup."""

import importlib.util
import json
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def test_runtime_baseline_with_only_approved_cleanup_and_same_config_schema():
    assert tool("check_repository").baseline_errors() == []
    baseline = json.loads((ROOT / "docs/baseline-1.2.1.json").read_text())
    assert baseline["config_entry_version"] == 3 and baseline["config_entry_minor_version"] == 1
    assert set(baseline["approved_cleanup"]) == {"migration.py"}


@pytest.mark.parametrize(
    "path",
    [".venv/key", "dist/archive.zip", "../private", ".git/config", ".package-tmp/token", "private.json"],
)
def test_publication_scope_excludes_private_workspace(path):
    assert not tool("repository_files").allowed(Path(path))


def test_secret_scanner_detects_values_but_never_echoes_them():
    scanner = tool("secret_scan")
    value = "ghp_" + "A" * 30
    findings = scanner.scan(Path("tests/case.py"), value.encode())
    assert findings and all(value not in finding for finding in findings)
    assert scanner.scan(Path("tests/case.py"), b'token = "dummy"') == []
    host = ".".join(("192", "168", "42", "42"))
    assert scanner.scan(Path("tests/case.py"), f'url = "http://{host}:1234/api/v1/models"'.encode())


def test_workflows_parse_and_have_no_mutation_permissions_or_publish_job():
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        data = yaml.safe_load(path.read_text())
        assert data["permissions"] == {"contents": "read"}
        for job in data["jobs"].values():
            assert "permissions" not in job or "write" not in job["permissions"].values()
            for step in job.get("steps", []):
                assert not any(
                    command in step.get("run", "") for command in ("git push", "gh release", "gh repo create")
                )
                if step.get("uses", "").startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] is False


def test_hacs_layout_and_local_icons_match_documented_versions():
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["zip_release"] is False and hacs["hide_default_branch"] is True
    for path in (ROOT / "custom_components/assist_router/brand").glob("*.png"):
        with Image.open(path) as image:
            expected = 512 if "@2x" in path.name else 256
            assert image.mode == "RGBA" and image.size == (expected, expected)
            assert image.getchannel("A").getextrema() == (0, 255)
    for path in (ROOT / "assets").glob("*.svg"):
        tree = ElementTree.parse(path)
        assert tree.getroot().get("viewBox") == "0 0 256 256"
        assert not any(node.tag.endswith("script") or node.tag.endswith("image") for node in tree.iter())


def test_repository_metadata_and_hygiene_pass():
    assert tool("check_repository").validate(tag="v1.2.1") == []
