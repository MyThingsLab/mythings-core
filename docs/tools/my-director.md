---
tool: MyDirector
repo: my-director
package: mydirector
status: designed
added: 2026-07-12
backlog_label: my-director
engine_call: explain why the fleet did this, from its ledger entries and the diff
ledger_kinds: [direct, merged, halted, planned, explained]
depends_on: [tool:my-conductor, tool:my-planner, tool:my-reporter, tool:my-guard]
---

# MyDirector — design plan

## Purpose

The fleet's **control plane**: turns the operator's supervisory decision into an
action, and explains the fleet's behaviour back to them.

Everything else in the fleet decides *for itself* — MyPlanner recommends a
sequence, MyOrchestrator picks the next issue, MyConductor recommends a merge
order, fleet_dispatch spawns the workers. The human's only interface to any of it
was `mytelegrambot notify`: step 9 of a 9-step cycle, firing after every decision
had already been made, pushing raw ledger lines.

MyDirector is where the operator's *authority* lives. It is the answer to
"supervise, plan and direct the fleet from a phone".

## Why this is not just more MyTelegramBot

The obvious move — put `/prs`, `/merge`, `/plan`, `/why` in the bot — is wrong,
but **not for the reason it first appears**.

It is a common misreading that the bot "may not act". It already does: the
`Close idea` button performs a `gh issue close` through the same `Policy` seam
every other GitHub write in the fleet passes. Its `no Workspace — no code edits,
no PR ever` invariant means *never author code or open a PR*. It does not mean
"never write".

The bot's two real prohibitions are narrower, and both are about **judgment**:

1. **It never calls the Engine itself.** Every Engine call is delegated wholesale
   to the owning tool's already-shipped code — MyIdea's `explore()`, MyNotes'
   `tag()`, MyGuide's `wish()`.
2. **It never composes prose** over what it relays.

So the reasons MyDirector exists are these, and only these:

- **`why` needs an Engine-call owner, and the bot may never be one.** A tool with
  a contract has to own that call.
- **Blast radius.** The bot is now the fleet's **ask channel** (`MYTHINGS_ASK_CMD`
  → `mytelegrambot ask`): every unattended `ASK` in every worker resolves through
  it. Its failure mode must stay *"no message delivered"*. If the same process
  also decides which PR to merge, a bug in the comms tool can merge the wrong PR
  **and** take out ASK escalation fleet-wide at the same moment. The transport is
  load-bearing, so it stays thin.
- **Fleet control is a domain, not plumbing.** "Which PRs are mergeable, in what
  order" is a real question — MyConductor is designed to answer it and explicitly
  **never merges**. Something must execute the order it recommends. That something
  is not the transport.

## The single Engine call

> Explain why the fleet did this, from its ledger entries and the diff.

`why` is the only one. A digest line is terminal — you read that a worker did
something and cannot ask a follow-up without opening a laptop. `why` takes a
ledger entry (or a PR) and returns a plain-language account of what the fleet was
doing and why, grounded in the entries and the diff. Nothing is fabricated: if the
ledger does not say, the answer says it does not say.

Every other verb is **deterministic**: listing mergeable PRs, executing a merge,
touching the halt marker, recording a plan decision.

## Invariants

- **Never merges autonomously — and the `Policy` enforces that, not this tool's
  good manners.** MyDirector *proposes* a merge by evaluating a
  `myguard.MERGE_ACTION` (`pr-merge`) Action. MyGuard answers **ASK**, which means:
  unattended, with no ask channel, it collapses to `DENY` and nothing merges; with a
  human reachable, it becomes a real Allow/Deny prompt on their phone. **The tap is
  the human merging** — which is what the fleet rule always required, and what until
  now cost a trip to a laptop.

  This is deliberately *not* a bespoke button. It rides the ask channel, which is
  already fail-closed, already operator-only (an ask prompt goes only to
  `TELEGRAM_CHAT_ID`, and the daemon drops `ASK_DECISIONS` callbacks from every other
  chat), and carries no client-supplied `callback_data` naming a PR that could be
  forged. The fiddliest, most security-sensitive part of merge-from-chat was already
  solved by machinery built for another reason.

  **No Engine call may ever cause a merge.** The Engine may explain a merge; it may
  never decide one.

  *This invariant was nearly a lie:* a structured merge Action matched no MyGuard
  rule, fell through to the permissive default, and came back `ALLOW` — unattended,
  no human. MyDirector would have merged on its own while its design doc claimed it
  could not. Fixed in `my-guard#11`; the lesson is that an invariant a tool merely
  *intends* is not an invariant.
- **No `Workspace`.** It never authors code and never opens a PR. It merges,
  halts, and records decisions about PRs *other tools authored*.
- **Every write passes `Policy`**, the same seam as every other GitHub write in
  the fleet.
- **Only the operator directs.** A tester may never reach any verb here. The
  distinction already exists in `mytelegrambot.authz`; MyDirector must not
  re-derive it, and must never trust a chat id it was handed as authority.
- **Never dispatches work.** Spawning workers stays fleet_dispatch's job; choosing
  the next issue stays MyOrchestrator's. MyDirector *approves* a plan; it does not
  make one.
- **Advice in, action out.** It consumes MyConductor's recommended order, but a
  recommendation is not a mandate: the operator may merge out of order, and
  MyDirector must say what that breaks rather than refuse or silently comply.

## Verbs

| verb | Engine? | writes? | what it is |
|---|---|---|---|
| `status` | no | no | what the fleet is doing, what it cost, what is stuck |
| `prs` | no | no | open PRs that are green and mergeable, in MyConductor's order. Read-only, so the operator can *pull* the state — the ask channel is push-only and cannot answer "what can I merge right now?" |
| `merge <pr>` | no | **yes** | proposes a `pr-merge` Action; MyGuard answers ASK, the operator taps, and *that* is the merge |
| `halt` / `resume` | no | yes (marker file) | the kill switch |
| `plan` | no | yes (plan ledger) | render MyPlanner's sequence; record approve/reorder/skip |
| `why <ref>` | **yes** | no | the one Engine call |

## How it reaches the human

Rendered through **MyTelegramBot**, which imports it as a library — the precedent
MyGuide already set and the bot's own contract already names: *"this tool imports
any tool whose structured result it must render in one synchronous reply."*
MyDirector returns structured results (`PullRequest`, `Plan`, `Explanation`); the
bot renders them and routes the button taps back. The bot gains no Engine call and
no `Workspace`, ever.

## Carve-out: `/halt` does not wait for this tool

`halt` / `resume` have no Engine call, no prose and no judgment — they touch a
marker file (`.fleet-dispatch/HALT`). The kill switch is currently a file you
`touch` from a terminal, which means **the fleet's most safety-critical control is
unreachable exactly when the unattended, billed loop is running.** Making that wait
on a whole new tool is backwards.

The bot ships `/halt` immediately as a **CLI hand-off** to `fleet_dispatch.py
--abort` / `--clear-halt` — the fleet's normal cross-tool relationship, needing no
import, no Engine and no `Workspace`. MyDirector adopts it later if it earns the
right to.

## Open questions

- **Where does the halt marker really belong?** A bot (or MyDirector) reaching into
  `.fleet-dispatch/HALT` is a coupling smell: that is fleet_dispatch's private
  state. A `mythings.halt` core seam — one marker, one reader, many arms — may be
  the honest shape once a second thing needs to halt the fleet.
- ~~**Does `merge` belong behind `ask` instead of behind a bespoke button?**~~
  **Resolved: yes.** It collapses two mechanisms into one, and the survivor was
  already fail-closed and already operator-only. See `my-guard#11` and the analysis
  on `fleet-dispatch#42`. The cost is honest: the ask channel is **push-only**, so
  the operator cannot ask "what can I merge right now?" — which is why `prs` stays,
  read-only.
- **How many unanswered asks is a merge pass allowed to cost?** Each blocks up to
  300s. Ten PRs with the operator asleep is fifty minutes of a cycle spent timing
  out, one prompt at a time. There needs to be a "nobody is home, stop asking" rule.
- **What is `status` when the fleet spans 30 repos?** It cannot be a wall of text.
  This likely wants MyDashboard's existing render rather than a new one.
