"""Version/HACS baseline with the sole approved legacy-URL cleanup and scan."""

import argparse
import ast
import hashlib
import json
import tomllib

from PIL import Image
from repository_files import ROOT
from secret_scan import scan_all


def baseline_errors(root=ROOT):
    baseline = json.loads((root / "docs/baseline-1.2.1.json").read_text(encoding="utf-8"))
    component = root / "custom_components/assist_router"
    errors = []
    cleanup = baseline.get("approved_cleanup", {})
    if set(cleanup) != {"migration.py"}:
        errors.append("Only the reviewed migration URL cleanup is allowed")
    for relative, digest in baseline["component_sha256"].items():
        if relative == "manifest.json":
            continue
        if relative in cleanup:
            if cleanup[relative]["original_sha256"] != digest:
                errors.append("Cleanup original hash differs from baseline")
            digest = cleanup[relative]["approved_sha256"]
            tree = ast.parse((component / relative).read_text(encoding="utf-8"))
            ast_digest = hashlib.sha256(ast.dump(tree, include_attributes=False).encode("utf-8")).hexdigest()
            if ast_digest != cleanup[relative]["ast_without_default_sha256"]:
                errors.append("Cleanup AST differs from original with only URL fallback removed")
        path = component / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(f"Runtime baseline changed: {relative}")
    before = baseline["manifest_before"]
    after = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    cosmetic = {"codeowners", "documentation", "issue_tracker"}
    if {k: v for k, v in before.items() if k not in cosmetic} != {
        k: v for k, v in after.items() if k not in cosmetic
    }:
        errors.append("Functional manifest metadata changed")
    allowed_assets = {"brand/icon.png", "brand/icon@2x.png", "brand/dark_icon.png", "brand/dark_icon@2x.png"}
    for path in component.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        name = path.relative_to(component).as_posix()
        if name not in baseline["component_sha256"] and name not in allowed_assets:
            errors.append(f"Unexpected runtime addition: {name}")
    return errors


def validate(root=ROOT, tag=None):
    errors = baseline_errors(root)
    manifest = json.loads(
        (root / "custom_components/assist_router/manifest.json").read_text(encoding="utf-8")
    )
    hacs = json.loads((root / "hacs.json").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    base = "https://github.com/BugsDan/ha-assist-router"
    if manifest["version"] != "1.2.1" or project["project"]["version"] != manifest["version"]:
        errors.append("Public baseline must remain 1.2.1")
    if tag is not None and tag != "v1.2.1":
        errors.append("Expected baseline tag v1.2.1")
    if manifest["domain"] != "assist_router" or manifest["codeowners"] != ["@BugsDan"]:
        errors.append("Domain/owner mismatch")
    if manifest.get("documentation") != base or manifest.get("issue_tracker") != base + "/issues":
        errors.append("Target repository links missing")
    folders = [
        p.name for p in (root / "custom_components").iterdir() if p.is_dir() and not p.name.startswith("_")
    ]
    if folders != ["assist_router"]:
        errors.append("HACS requires exactly one integration")
    if hacs != {
        "name": "Assist Router",
        "homeassistant": "2026.10.2",
        "hide_default_branch": True,
        "content_in_root": False,
        "zip_release": False,
    }:
        errors.append("HACS tag-source policy mismatch")
    for name in ("icon", "dark_icon"):
        for suffix, size in (("", 256), ("@2x", 512)):
            with Image.open(root / f"custom_components/assist_router/brand/{name}{suffix}.png") as image:
                if (
                    image.mode != "RGBA"
                    or image.size != (size, size)
                    or image.getbbox() != (0, 0, size, size)
                ):
                    errors.append("PNG must be square, transparent RGBA and trimmed")
    for name in (
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "docs/GITHUB_HACS.md",
        "docs/BRANDING.md",
        "docs/ROADMAP.md",
        "docs/RELEASE_1.2.1.md",
    ):
        if not (root / name).is_file():
            errors.append(f"Missing {name}")
    return errors + scan_all(root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    args = parser.parse_args()
    errors = validate(tag=args.tag)
    for error in errors:
        print(error)
    print(f"Repository review: {len(errors)} findings; runtime baseline 1.2.1.")
    raise SystemExit(bool(errors))
