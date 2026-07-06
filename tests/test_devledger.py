from pathlib import Path

from mythings._devledger import add_entry, main, read_all


def test_add_writes_to_per_session_file_with_metadata(tmp_path: Path) -> None:
    add_entry(
        "sess-a",
        "decision",
        detail="StrEnum over (str, Enum)",
        root=tmp_path,
        commit="eba8f7f",
    )
    entries = read_all(tmp_path)
    assert (tmp_path / "dev-ledger" / "sess-a.jsonl").exists()
    assert len(entries) == 1
    assert entries[0].kind == "decision"
    assert entries[0].data["session"] == "sess-a"
    assert entries[0].data["commit"] == "eba8f7f"
    # Empty optional fields are dropped, not stored blank.
    assert "pr" not in entries[0].data


def test_read_all_merges_sessions_and_sorts_by_ts(tmp_path: Path) -> None:
    add_entry("s2", "build", detail="second", root=tmp_path, ts="2026-07-06T12:00:00Z")
    add_entry("s1", "scaffold", detail="first", root=tmp_path, ts="2026-07-05T09:00:00Z")
    add_entry("s2", "ship", detail="third", root=tmp_path, ts="2026-07-07T15:00:00Z")

    details = [e.detail for e in read_all(tmp_path)]
    assert details == ["first", "second", "third"]


def test_read_all_can_scope_to_one_session(tmp_path: Path) -> None:
    add_entry("s1", "build", detail="a", root=tmp_path)
    add_entry("s2", "build", detail="b", root=tmp_path)
    assert [e.detail for e in read_all(tmp_path, session="s2")] == ["b"]


def test_read_all_on_empty_repo_is_empty(tmp_path: Path) -> None:
    assert read_all(tmp_path) == []


def test_main_add_then_show(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = main(["add", "build", "--detail", "did a thing", "--session", "s", "--commit", "abc"])
    assert rc == 0
    assert main(["show"]) == 0
    out = capsys.readouterr().out
    assert "did a thing" in out
    assert "commit=abc" in out
