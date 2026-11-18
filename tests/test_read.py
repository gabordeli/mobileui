from types import SimpleNamespace

import pytest

from deluge_mobileui import read


class FakeTorrent:
    def __init__(self, torrent_id, **fields):
        self.torrent_id = torrent_id
        self.fields = fields
        self.update_flags = []

    def get_status(self, keys, update=False):
        self.update_flags.append(update)
        return {key: self.fields.get(key) for key in keys}

    def get_files(self):
        return [
            {"index": 0, "path": "file0.mkv", "size": 10, "offset": 0},
            {"index": 1, "path": "file1.mkv", "size": 20, "offset": 10},
            {"index": 2, "path": "file2.mkv", "size": 30, "offset": 30},
        ]

    def get_file_progress(self):
        return [0.1, 0.2, 0.3]

    def get_file_priorities(self):
        return [4, 1, 0]


class FakeCore:
    def __init__(self, torrents, config=None):
        self.torrentmanager = SimpleNamespace(torrents=torrents)
        self.config = config or {}
        self.free_space = 4096
        self.session = SimpleNamespace(is_paused=lambda: False)

    def get_session_status(self, keys):
        return {key: 1 for key in keys}

    def get_config_values(self, keys):
        return {key: self.config.get(key) for key in keys}

    def get_free_space(self, path):
        if self.free_space is None:
            raise OSError(path)
        return self.free_space


class FakeLabel:
    def __init__(self, mapping, labels=None):
        self.torrent_labels = mapping
        self.labels = labels if labels is not None else sorted(set(mapping.values()))

    def get_labels(self):
        return self.labels


def make_torrent(torrent_id, name, state="Paused", progress=0.0, eta=-1, time_added=0):
    return FakeTorrent(
        torrent_id,
        name=name,
        state=state,
        progress=progress,
        download_payload_rate=0,
        upload_payload_rate=0,
        eta=eta,
        ratio=1.0,
        total_size=100,
        save_path="/downloads",
        time_added=time_added,
    )


def make_core(*torrents):
    return FakeCore({torrent.torrent_id: torrent for torrent in torrents})


def test_list_filters_sorts_and_paginates():
    core = make_core(
        make_torrent("a", "Dune", state="Seeding", progress=100.0),
        make_torrent("b", "Alien", state="Paused", progress=10.0),
        make_torrent("c", "Blade Runner", state="Paused", progress=50.0),
    )
    labels = FakeLabel({"a": "movies", "c": "movies"})

    result = read.list_torrents(
        core, labels, state="Paused", q="e", sort="name", offset=0, limit=10
    )

    assert result["total"] == 2
    assert [row["name"] for row in result["torrents"]] == ["Alien", "Blade Runner"]
    assert result["torrents"][1]["label"] == "movies"
    assert result["torrents"][0]["label"] == read.NO_LABEL
    assert core.torrentmanager.torrents["a"].update_flags == [False]


def test_list_includes_the_status_message():
    torrent = make_torrent("a", "Dune")
    torrent.fields["message"] = "Tracker error"
    core = make_core(torrent)

    result = read.list_torrents(core, FakeLabel({}))

    assert result["torrents"][0]["message"] == "Tracker error"


def test_list_filters_by_label_and_paginates():
    core = make_core(
        make_torrent("a", "One", progress=10.0),
        make_torrent("b", "Two", progress=20.0),
        make_torrent("c", "Three", progress=30.0),
    )
    labels = FakeLabel({"a": "movies", "b": "movies"})

    result = read.list_torrents(
        core, labels, label="movies", sort="-progress", offset=1, limit=1
    )

    assert result["total"] == 2
    assert result["offset"] == 1
    assert result["limit"] == 1
    assert [row["name"] for row in result["torrents"]] == ["One"]


def test_list_sorts_eta_with_infinity_last():
    core = make_core(
        make_torrent("a", "NoEta", eta=-1),
        make_torrent("b", "Ten", eta=10),
        make_torrent("c", "Five", eta=5),
    )

    result = read.list_torrents(core, None, sort="eta")

    assert [row["name"] for row in result["torrents"]] == ["Five", "Ten", "NoEta"]


def test_list_sorts_by_time_added():
    core = make_core(
        make_torrent("a", "Old", time_added=100),
        make_torrent("b", "Newest", time_added=300),
        make_torrent("c", "Middle", time_added=200),
    )

    result = read.list_torrents(core, None, sort="-time_added")

    assert [row["name"] for row in result["torrents"]] == [
        "Newest",
        "Middle",
        "Old",
    ]
    assert result["torrents"][0]["time_added"] == 300


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"sort": "bogus"}, "unknown sort field"),
        ({"limit": 0}, "limit must be"),
        ({"limit": 500}, "limit must be"),
        ({"offset": -1}, "offset must be"),
    ],
)
def test_list_validates_query(kwargs, message):
    core = make_core()

    with pytest.raises(ValueError, match=message):
        read.list_torrents(core, None, **kwargs)


def test_detail_includes_label_and_status_only():
    torrent = make_torrent("a", "Dune")
    core = make_core(torrent)

    result = read.get_torrent(core, FakeLabel({"a": "movies"}), "a")

    assert result["id"] == "a"
    assert result["label"] == "movies"
    assert "files" not in result
    assert "file_progress" not in result
    assert torrent.update_flags == [True]


def test_files_are_paginated():
    core = make_core(make_torrent("a", "Dune"))

    result = read.get_files(core, "a", offset=1, limit=1)

    assert result["total"] == 3
    assert result["offset"] == 1
    assert result["limit"] == 1
    assert result["files"] == [
        {
            "index": 1,
            "path": "file1.mkv",
            "size": 20,
            "offset": 10,
            "progress": 0.2,
            "priority": 1,
        }
    ]


def test_files_filter_before_pagination():
    core = make_core(make_torrent("a", "Dune"))

    result = read.get_files(core, "a", offset=0, limit=1, q="FILE1")

    assert result["total"] == 1
    assert result["files"][0]["path"] == "file1.mkv"


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"limit": 0}, "limit must be"),
        ({"limit": 501}, "limit must be"),
        ({"offset": -1}, "offset must be"),
    ],
)
def test_files_validate_query(kwargs, message):
    core = make_core(make_torrent("a", "Dune"))

    with pytest.raises(ValueError, match=message):
        read.get_files(core, "a", **kwargs)


def test_files_unknown_torrent():
    core = make_core()

    with pytest.raises(KeyError):
        read.get_files(core, "missing")


def test_session_returns_queue_and_count():
    core = FakeCore({"a": make_torrent("a", "Dune")}, {"max_active_limit": 3})

    result = read.get_session(core)

    assert result["num_torrents"] == 1
    assert result["queue"]["max_active_limit"] == 3
    assert result["free_space"] == 4096
    assert result["paused"] is False
    assert "version" in result


def test_session_free_space_failure_is_null():
    core = FakeCore({"a": make_torrent("a", "Dune")})
    core.free_space = None

    result = read.get_session(core)

    assert result["free_space"] is None


def test_session_negative_free_space_is_null():
    core = FakeCore({"a": make_torrent("a", "Dune")})
    core.free_space = -1

    result = read.get_session(core)

    assert result["free_space"] is None


def test_matching_ids_applies_filters():
    core = make_core(
        make_torrent("a", "Dune", state="Downloading"),
        make_torrent("b", "Dune Messiah", state="Paused"),
        make_torrent("c", "Other", state="Downloading"),
    )
    labels = FakeLabel({"a": "movies", "b": "movies", "c": "books"})

    result = read.matching_ids(core, labels, state="Downloading", label="movies")

    assert result["ids"] == ["a"]
    assert result["total"] == 1


def test_matching_ids_caps_the_list_but_reports_total():
    core = make_core(*[make_torrent(str(i), f"T{i}") for i in range(3)])

    result = read.matching_ids(core, FakeLabel({}), limit=2)

    assert len(result["ids"]) == 2
    assert result["total"] == 3
    assert result["limit"] == 2


def test_labels_counts_only_existing_torrents():
    core = make_core(make_torrent("a", "One"), make_torrent("b", "Two"))
    labels = FakeLabel({"a": "movies", "gone": "movies"})

    result = read.get_labels(labels, core)

    assert result["labels"] == [{"id": "movies", "count": 1}]
    assert result["no_label"] == 1


def test_labels_without_plugin():
    result = read.get_labels(None, make_core(make_torrent("a", "One")))

    assert result == {"labels": [], "no_label": 1}
