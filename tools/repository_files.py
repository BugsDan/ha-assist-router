"""Explicit publication boundary; no parent workspace, archives or environments."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_FILES = {
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "hacs.json",
    "pyproject.toml",
    "requirements-test.txt",
    "requirements-test-ha.txt",
    ".gitignore",
    ".gitattributes",
    ".gitleaks.toml",
}
TOP_DIRS = {"custom_components", "tests", "tests_live", "tools", "reference", "docs", "assets", ".github"}
EXCLUDE = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv", ".git", "dist", ".package-tmp"}


def allowed(path):
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and not set(path.parts) & EXCLUDE
        and path.suffix not in {".pyc", ".pyo"}
        and (path.as_posix() in TOP_FILES or len(path.parts) > 1 and path.parts[0] in TOP_DIRS)
    )


def public_files(root=ROOT):
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and allowed(path.relative_to(root))
    )
