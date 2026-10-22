import json
from pathlib import Path

from custom_components.smartcamper_suite.const import VERSION
from custom_components.smartcamper_suite.frontend import RESOURCE_URL

ROOT = Path(__file__).parents[1]


def test_beta_release_metadata_is_consistent():
    manifest = json.loads((ROOT / "custom_components/smartcamper_suite/manifest.json").read_text())
    package = json.loads((ROOT / "frontend/package.json").read_text())
    lockfile = json.loads((ROOT / "frontend/package-lock.json").read_text())

    assert VERSION == "0.3.0-beta.1"
    assert manifest["version"] == VERSION
    assert package["version"] == VERSION
    assert lockfile["packages"][""]["version"] == VERSION
    assert RESOURCE_URL == f"/smartcamper_suite/smartcamper-card.js?v={VERSION}"


def test_beta_docs_keep_stable_and_safety_boundaries_visible():
    for name in ("README.md", "README.en.md"):
        text = (ROOT / name).read_text()
        assert "0.3.0-beta.1" in text
        assert "HACS" in text
        assert "Legacy" in text or "legacy" in text
        assert "VM 104" in text

    notes = (ROOT / "docs/releases/v0.3.0-beta.1.md").read_text()
    assert "Deutsch" in notes
    assert "English" in notes
    assert "Nakordoni" in notes
    assert "Dry-Run" in notes
