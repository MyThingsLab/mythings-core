from __future__ import annotations

import argparse
import datetime
import os
from pathlib import Path

from mythings.ledger import Ledger, LedgerEntry

# Build-provenance tooling, not a contract: it records how a MyThingsLab repo was
# built, using the same ledger schema a shipped tool uses at runtime. Invoked as
# `python -m mythings._devledger`. Deliberately not exported from the package.

LEDGER_DIR = "dev-ledger"
KINDS = ("scaffold", "build", "decision", "fix", "ship")
_TAIL_FIELDS = ("commit", "pr", "supersedes")


def _default_session() -> str:
    return (
        os.environ.get("MYTHINGS_SESSION")
        or os.environ.get("CLAUDE_SESSION_ID")
        or datetime.date.today().isoformat()
    )


def _path(root: Path, session: str) -> Path:
    return root / LEDGER_DIR / f"{session}.jsonl"


def add_entry(
    session: str,
    kind: str,
    *,
    detail: str,
    outcome: str = "success",
    root: Path | None = None,
    ts: str | None = None,
    **data: str,
) -> LedgerEntry:
    root = root or Path.cwd()
    payload = {"session": session, **{k: v for k, v in data.items() if v}}
    fields = dict(tool="claude-code", kind=kind, outcome=outcome, detail=detail, data=payload)
    entry = LedgerEntry(ts=ts, **fields) if ts else LedgerEntry(**fields)
    return Ledger(_path(root, session)).append(entry)


def read_all(root: Path | None = None, *, session: str | None = None) -> list[LedgerEntry]:
    root = root or Path.cwd()
    directory = root / LEDGER_DIR
    files = [_path(root, session)] if session else sorted(directory.glob("*.jsonl"))
    entries = [e for f in files if f.exists() for e in Ledger(f)]
    entries.sort(key=lambda e: e.ts)
    return entries


def _format(entry: LedgerEntry) -> str:
    tail = " ".join(f"{k}={entry.data[k]}" for k in _TAIL_FIELDS if entry.data.get(k))
    line = f"{entry.ts}  {entry.kind:<9}  {entry.outcome:<8}  {entry.detail}"
    return f"{line}  [{tail}]" if tail else line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mythings._devledger",
        description="MyThingsLab build-provenance ledger — how a repo was built, start to ship.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="append a build-ledger entry to this session's file")
    add.add_argument("kind", help=f"suggested: {', '.join(KINDS)} (free-form allowed)")
    add.add_argument("--detail", required=True, help="one-sentence rationale — the 'why'")
    add.add_argument("--outcome", default="success")
    add.add_argument("--session", default=_default_session())
    add.add_argument("--commit", help="commit sha this entry explains")
    add.add_argument("--pr", help="PR number or url")
    add.add_argument("--files", help="comma-separated files touched")
    add.add_argument("--supersedes", help="commit/decision this replaces")
    add.add_argument("--ts", help="ISO timestamp; defaults to now (used to backfill history)")

    show = sub.add_parser("show", help="print the whole trail across sessions, oldest first")
    show.add_argument("--session", help="limit to one session file")
    show.add_argument("--kind", help="limit to one kind (e.g. decision)")

    args = parser.parse_args(argv)
    if args.cmd == "add":
        add_entry(
            args.session,
            args.kind,
            detail=args.detail,
            outcome=args.outcome,
            ts=args.ts,
            commit=args.commit or "",
            pr=args.pr or "",
            files=args.files or "",
            supersedes=args.supersedes or "",
        )
        return 0
    for entry in read_all(session=args.session):
        if args.kind and entry.kind != args.kind:
            continue
        print(_format(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
