# Third-party reference sources

Files under `reference/homeassistant/` and `reference/pyproject.toml` are unmodified
reference material from Home Assistant Core, tag 2026.10.2:
https://github.com/home-assistant/core/tree/2026.10.2

Copyright the Home Assistant contributors. Licensed under the Apache License 2.0.
See `reference/LICENSE.md`. They are used only for source contract tests and are
not included in the installable integration ZIP. Source URLs and SHA-256 hashes
are recorded in `docs/ha_api_evidence.json`.

No Home Assistant core code is copied into the installed integration.

The additional audit reference files under `reference/prompt_compatibility/local/`
come from skye-harris/hass_local_openai_llm, pinned commit
37b2334b2c5e5085a0c1081092fff238980e27ac (release tag 1.13.0).
Copyright their respective contributors; Apache License 2.0, included as
`reference/prompt_compatibility/local/LICENSE`. The additional core audit copies
under `reference/prompt_compatibility/core/` retain the Home Assistant license
described above. All are test/reference material, not installed router code.

## License boundary for publication

The MIT license at repository root covers original Assist Router code, original
repository tooling/documentation and the original SVG/PNG assets. It does not
relicense reference sources. All files under reference/ retain their upstream
licenses and attribution; copies of the Home Assistant and Local OpenAI Apache
2.0 licenses are retained at reference/LICENSE.md and
reference/prompt_compatibility/local/LICENSE. No third-party library binaries or
provider implementation code are shipped inside the installable integration.

Reference sources are included only in the publication/source archive to make
source-contract tests reproducible. They are excluded from the manual install ZIP.
Python development packages (including Pillow, Jinja2 and PyYAML) and the Gitleaks
binary are not redistributed as part of either archive. The Gitleaks download and
checksum provenance is recorded in docs/secret-scanner-provenance.json.

License sources: https://opensource.org/license/mit and
https://www.apache.org/licenses/LICENSE-2.0 (reviewed 2026-10-25).
