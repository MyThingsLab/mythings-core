# MyReporter — design plan

## Purpose

Reads the shared `Ledger` and each repo's `dev-ledger/`, posts a digest as a
GitHub issue comment (or prints markdown). Package `myreporter`, backlog
label `my-reporter`.

## The single Engine call

Optional. Deterministic by default — the digest is a templated summary of
ledger entries (counts by tool/kind/outcome, recent PRs, recent decisions).
If `--summarize` is passed, one Engine call turns the deterministic digest
into a paragraph of prose:

- **Input:** `EngineRequest.prompt` = the deterministic markdown digest
  verbatim (already fully computed; the model only rewrites it as prose,
  it never sees raw ledger data it could hallucinate against).
- **Output:** `EngineResult.text` = one paragraph, appended under the
  digest's tables, not replacing them.
- Against `NoopEngine`: empty reply, so `--summarize` degrades to "digest
  only, no prose" — still a complete, useful report.

## Deterministic pre-work

1. Read the target repo's shared `Ledger` (path given, e.g.
   `.mythings/ledger.jsonl` or wherever the workspace convention places it)
   and its `dev-ledger/*.jsonl` files.
2. Merge both streams, sort by `ts`.
3. Filter to a window (`--since <ISO8601>`, default: since the last
   `MyReporter` `kind=report` entry, else all-time).
4. Aggregate: counts per `tool`, per `kind`, per `outcome`; list of
   `kind=ship`/`kind=decision` entries verbatim (these are the
   highest-signal lines); list of open PRs referenced in `data.pr` whose
   ledger entry has no matching later `outcome` update (i.e. still pending).
5. Render as one markdown document (tables + a bullet list of decisions).

## Ledger

- **Writes:** `kind=report`, `outcome=success`, `detail`="digest for
  <window>", `data={window_start, window_end, entries_count,
  comment_url|None}`. This entry is what makes "since last report"
  incremental in step 3.
- **Reads:** the full merged ledger + dev-ledger stream (read-only, never
  mutates other tools' entries).

## Guard & Workspace

- No `Workspace` needed — MyReporter only reads files and optionally posts a
  comment; it never edits the target repo's tree or opens a PR.
- The only side effect is `gh issue comment` (or `gh pr comment`), which is
  still an `Action(kind="bash", ...)` run through `Policy` — commenting isn't
  in MyGuard's default deny/ask rules, so it resolves `ALLOW` by default,
  but the seam is still there for a repo that wants to restrict it.
- No PR is ever opened by MyReporter — it is the one tool with zero repo
  write access beyond a comment.

## CLI surface

```
myreporter digest [--since ISO8601] [--repo owner/name] [--handoff]
myreporter post --issue <number> [--since ISO8601] [--summarize] [--handoff]
```

`digest` prints markdown to stdout (dev loop / CI job summary); `post`
comments it on an issue.

## Handoff mode (`--handoff`)

Same merged/windowed entries, different render: instead of the aggregate
digest (counts + verbatim decisions/ships + pending PRs), it produces a
resume-context brief aimed at a new session or agent picking the work back
up, not a human activity report:

- **Open threads** — `kind=ask`/`kind=drift` entries in the window (things a
  prior session flagged as needing judgment or attention).
- **Recent decisions** — the last few `kind=decision` entries verbatim (the
  *why*, which is exactly what a resuming session would otherwise have to
  re-derive from git history).
- **Pending PRs** — same computation as the digest's pending-PR list.
- **Last shipped** — the most recent `kind=ship` entry, so the reader knows
  where the fleet left off.
- Empty window → `"Clean baseline — nothing pending, no open threads."`,
  not an exception.

`--summarize` composes with `--handoff` unchanged — it's the same Engine
seam (rewrite the already-computed markdown as prose), just fed the handoff
markdown instead of the digest markdown. No new Engine call was introduced;
this is a second deterministic renderer over the same windowed entries.

## Test plan

- **Happy path:** a fixture ledger + dev-ledger with a mix of `build`,
  `decision`, `ship` entries; assert the rendered markdown contains correct
  counts and lists decisions verbatim.
- **Edge case (empty ledger):** no entries in the window; assert a
  graceful "nothing to report" digest, not an exception, and `outcome=success`
  still written (an empty report is a valid report).
- Mock only `github.Runner` for the `post` subcommand; ledger reads are
  against real temp JSONL fixture files.

## Dependencies & build order

Depends only on core `ledger` and `github` (read-only use) — no `policy` or
`isolation` needed beyond the comment action. Build **after** MyTester (so
there's real ledger history worth reporting on) but it has no functional
dependency on any other tool; could be built in parallel.

**Open questions:**
- Ledger location convention for MyReporter to read across repos isn't
  settled yet — assume one `Ledger` per repo at a fixed path
  (`.mythings/ledger.jsonl`), not a cross-repo aggregate; a future
  `--repo` list could merge several.
- Whether `--summarize`'s one Engine call is worth the token cost vs. just
  shipping the deterministic tables — leaving it opt-in resolves this
  without deciding it now.
