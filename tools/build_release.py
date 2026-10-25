"""Build verified local publication and manual install ZIPs; never publish anything."""

import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from check_repository import validate
from repository_files import ROOT, allowed, public_files


def archive(target, members):
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(members):
            name = path.relative_to(ROOT).as_posix()
            assert allowed(path.relative_to(ROOT))
            info = ZipInfo(name, date_time=(2026, 10, 25, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            output.writestr(info, path.read_bytes())
    with ZipFile(target) as result:
        assert result.testzip() is None
        assert set(result.namelist()) == {path.relative_to(ROOT).as_posix() for path in members}
        for path in members:
            assert result.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()


def main():
    errors = validate()
    if errors:
        raise ValueError("Publication checks failed; run tools/check_repository.py")
    version = json.loads((ROOT / "custom_components/assist_router/manifest.json").read_text())["version"]
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    files = public_files()
    publication = dist / f"ha-assist-router-{version}-publication.zip"
    manual = dist / f"assist-router-{version}-public-baseline.zip"
    archive(publication, files)
    installed = [
        p
        for p in files
        if p.relative_to(ROOT).parts[0] in {"custom_components", "docs", "assets"}
        or p.name in {"README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"}
    ]
    archive(manual, installed)
    checksums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in (publication, manual)
    )
    (dist / "SHA256SUMS.txt").write_text(checksums, encoding="ascii")
    print(checksums, end="")
    print(f"Verified {len(files)} publication files; archive root is repository root, no extra folder.")


if __name__ == "__main__":
    main()
