import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "release_script", ROOT / "scripts" / "release.py"
)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def changelog(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_moves_the_unreleased_section(monkeypatch, tmp_path):
    path = changelog(
        tmp_path,
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "- Feature A.\n"
        "- Fix B.\n\n"
        "## [0.1.3] - 2026-11-17\n\n"
        "- Release 0.1.3.\n",
    )
    monkeypatch.setattr(release, "CHANGELOG", path)

    release.update_changelog("0.1.4")

    text = path.read_text(encoding="utf-8")
    unreleased = text.split("## [Unreleased]", 1)[1].split("## [0.1.4]", 1)[0]
    section = text.split("## [0.1.4]", 1)[1].split("## [0.1.3]", 1)[0]
    assert unreleased.strip() == ""
    assert "- Feature A." in section
    assert "- Fix B." in section
    assert "## [0.1.3]" in text


def test_empty_unreleased_falls_back(monkeypatch, tmp_path):
    path = changelog(
        tmp_path,
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "## [0.1.3] - 2026-11-17\n\n"
        "- Release 0.1.3.\n",
    )
    monkeypatch.setattr(release, "CHANGELOG", path)

    release.update_changelog("0.1.4")

    text = path.read_text(encoding="utf-8")
    section = text.split("## [0.1.4]", 1)[1].split("## [0.1.3]", 1)[0]
    assert "- Release 0.1.4." in section


def test_adds_unreleased_when_missing(monkeypatch, tmp_path):
    path = changelog(
        tmp_path,
        "# Changelog\n\n## [0.1.3] - 2026-11-17\n\n- Release 0.1.3.\n",
    )
    monkeypatch.setattr(release, "CHANGELOG", path)

    release.update_changelog("0.1.4")

    text = path.read_text(encoding="utf-8")
    assert (
        text.index("## [Unreleased]")
        < text.index("## [0.1.4]")
        < text.index("## [0.1.3]")
    )


def test_bump():
    assert release.bump("1.2.3", "patch") == "1.2.4"
    assert release.bump("1.2.3", "minor") == "1.3.0"
    assert release.bump("1.2.3", "major") == "2.0.0"
