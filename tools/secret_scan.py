"""Local publication hygiene scan. Report locations/rules, never matched values."""

import re

from repository_files import public_files

PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "openai-token": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
    "aws-access-key": re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}"),
    "credential-literal": re.compile(
        r"""(?:api[_-]?key|access[_-]?token|password|secret|token)["']?\s*[:=]\s*["'][A-Za-z0-9_./+=-]{20,}["']""",
        re.I,
    ),
    "personal-path": re.compile(
        r"(?:[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9_.-]+[\\/]|/home/[A-Za-z0-9_.-]+/)", re.I
    ),
    "private-endpoint": re.compile(
        r"https?://(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(?=[:/\s\"']|$)",
        re.I,
    ),
}


def scan(path, data):
    if path.suffix == ".png":
        return []
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{path}: unexpected binary file"]
    return [
        f"{path}:{number}: {rule}"
        for number, line in enumerate(content.splitlines(), 1)
        for rule, pattern in PATTERNS.items()
        if pattern.search(line)
    ]


def scan_all(root):
    return [
        finding for path in public_files(root) for finding in scan(path.relative_to(root), path.read_bytes())
    ]


if __name__ == "__main__":
    from repository_files import ROOT

    findings = scan_all(ROOT)
    for finding in findings:
        print(finding)
    print(f"Local publication scan: {len(findings)} findings; no values printed.")
    raise SystemExit(bool(findings))
