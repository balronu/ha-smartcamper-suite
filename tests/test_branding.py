import struct
from pathlib import Path

ROOT = Path(__file__).parents[1]


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_home_assistant_brand_assets_have_expected_dimensions_and_paths():
    expected = {
        "icon.png": (256, 256),
        "icon@2x.png": (512, 512),
        "logo.png": (256, 222),
        "logo@2x.png": (512, 444),
    }
    brand = ROOT / "custom_components" / "smartcamper_suite" / "brand"
    assert {path.name for path in brand.glob("*.png")} == set(expected)
    for name, size in expected.items():
        assert png_size(brand / name) == size


def test_readme_branding_and_module_assets_are_repository_local():
    for readme in (ROOT / "README.md", ROOT / "README.en.md"):
        text = readme.read_text()
        for asset in (
            "docs/assets/smartcamper-suite-logo-set.png",
            "docs/assets/module-travel-journal.svg",
            "docs/assets/module-fuel-stations.svg",
            "docs/assets/module-route-planner.svg",
            "docs/assets/module-border-forecast.svg",
        ):
            assert asset in text
            assert (ROOT / asset).is_file()
