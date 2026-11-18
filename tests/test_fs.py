import pytest

from deluge_mobileui import fs


def test_list_dirs_only_directories(tmp_path):
    (tmp_path / "B").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "file.txt").write_text("x")
    (tmp_path / "link").symlink_to(tmp_path / "B", target_is_directory=True)

    result = fs.list_dirs(str(tmp_path))

    assert result["path"] == str(tmp_path.resolve())
    assert result["parent"] == str(tmp_path.parent)
    assert result["writable"] is True
    assert [item["name"] for item in result["dirs"]] == ["a", "B", "link"]
    assert all(
        set(item) == {"name", "path", "writable"} for item in result["dirs"]
    )


def test_list_dirs_truncates(tmp_path, monkeypatch):
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(fs, "MAX_DIRS", 2)

    result = fs.list_dirs(str(tmp_path))

    assert len(result["dirs"]) == 2
    assert result["truncated"] is True


@pytest.mark.parametrize("path", [None, "", "relative/path"])
def test_list_dirs_requires_absolute_path(path):
    with pytest.raises(fs.BadRequest):
        fs.list_dirs(path)


def test_list_dirs_rejects_files_and_missing_paths(tmp_path):
    file_path = tmp_path / "file.txt"
    file_path.write_text("x")

    with pytest.raises(fs.BadRequest):
        fs.list_dirs(str(file_path))
    with pytest.raises(fs.BadRequest):
        fs.list_dirs(str(tmp_path / "missing"))


def test_list_dirs_reports_root_parent(tmp_path):
    result = fs.list_dirs("/")

    assert result["parent"] is None
    assert result["path"] == "/"
