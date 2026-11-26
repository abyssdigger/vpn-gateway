# COLLAB v2 — project Issue work plane, Unit 1

Status: staged implementation for independent review; not an active epoch.
The v0/v1 modules, protocol, configurations and current journal are unchanged.

## Boundary

This unit implements a pure task registry, material admission and relation reducer.
It does not implement acquisition, compact transport, preflight, publishing, Issue
closure, holder-command execution, health/receipt handling or epoch cutover.
Non-task control kinds are rejected by this unit, not silently ignored. Later
units must compose the holder/health/receipt/signal projections without creating
a second task lifecycle. The v1 signal wire may be reused through the physical
fact index.

The input is a trusted, complete normalized observation, not an arbitrary URL
or authority. Acquisition must prove completeness/stability separately.

## Configuration and discovery

The v2 config uses protocol "vpng-collab/2", repository, journal_rooms (fixed
control Issues), signal_room, journal_epoch, roles, projectholder and
command_registry. The pilot has GUARD (also SPEC) and BUILDER; their actor IDs may
be equal, but incarnations must be distinct. Role claims are cooperative and not
cryptographic authentication. The runtime role gate and write authority remain
external. A fresh epoch needs an explicitly reviewed clean control surface:
legacy framed events must not silently enter v2 replay.

Only fully structurally validated OPEN control facts from GUARD in a configured
control room discover a task. Task identity is a one-to-one binding of task key,
control room, configured repository, numeric Issue number and immutable Issue ID.
No dynamic Issue numbers in config. Neither prose nor RESULT/REVIEW references
discover tasks. Discovery is bounded and rejects rebindings before acquisition.
Full material admission remains necessary after discovery.

## Exact control wire

A control comment has first line "<!-- vpng-collab-journal/2 -->", then exactly
one fenced json object and no trailing prose. Fields are closed. Every event
carries protocol, journal_epoch, event_id, kind, room, from, to, incarnation,
task, revision. All task relations are single-recipient. OPEN, REVIEW and
DISPOSITION are GUARD -> BUILDER; RESULT is BUILDER -> GUARD.

OPEN adds task_ref = {issue_number, issue_id}, spec_ref and previous.
Revision 1: spec_ref = {kind:"issue_body",body_sha256}, previous = null.
Later revisions: spec_ref = {kind:"issue_comment",comment_id,body_sha256},
previous = exact SUPERSEDED disposition event ID of prior revision.
The immutable r1 Issue body remains bound for all revisions. Later SPEC comments
carry the complete new specification, not a delta or mutable body mirror.

RESULT adds open_id, previous, attempt, commit_sha, material_ref.
First result cites OPEN; later result cites exact prior REWORK and increments
attempt. REVIEW adds those same fields plus verdict (REWORK or ACCEPT);
previous cites exact RESULT. Its attempt and commit SHA must equal RESULT.
material_ref = {comment_id,body_sha256}, scoped to the registered Issue.

DISPOSITION adds open_id, previous and disposition. SUPERSEDED cites the exact
current relation head; a new revision is permitted only after explicit
supersession. CLOSED cites the ACCEPT head and adds accept_ref =
{room,comment_id,body_sha256} and close_event = {id,actor_id,created_at}.
accept_ref identifies a physical ACCEPT control occurrence, not just its logical
event ID. No alternative closure or automatic issue mutation exists in pilot.

## Work-plane material

Referenced task comments start with this hidden header (one strict JSON line):

    <!-- vpng-collab-task-material/2
    {"kind":"RESULT","task":"O1","revision":1,"attempt":1,"commit_sha":"<40hex>"}
    -->
    Candidate SHA: <same 40hex>

    Human-readable evidence prose

REVIEW adds verdict to the header and uses visible "GUARD ACCEPT: <sha>" or
"GUARD REWORK: <sha>" followed by nonempty substantive prose. SPEC r2+ header
has only kind SPEC, task, revision, followed by complete specification prose.
All header fields must match the referencing event exactly. Control records bind
the raw whole material body SHA-256; no substantive payload copy in control room.

## Observation contract

project_v2(cfg, control, tasks, previous=None) accepts control mapping keyed by
string journal-room number, values complete GitHub-style comment lists. Each
comment has id, user.id, body, created_at, updated_at. The dynamic task mapping
has exactly the discovered numeric Issue numbers as string keys. Each task
observation is normalized to:
- repository, number, id, is_pull_request, author_id, body, created_at;
- state (open/closed), closed_at and closed_by (numeric actor ID or null);
- comments (same shape as control), events (all relevant closed/reopened events
  normalized to {id,kind,actor_id,created_at}).

Only UTC second-resolution YYYY-MM-DDTHH:MM:SSZ timestamps are accepted.
Semantic comments must have created_at == updated_at; exact material predates
the referencing control fact; each causal relation strictly follows its
predecessor. Equality at timestamp precision is insufficient. This detects
observable edits, not same-second or otherwise unobserved history. The Issue
body is bound by exact bytes; aggregate Issue updated_at cannot prove its edit
history. Initial Issue author must be configured GUARD/SPEC for this pilot.
The observer must reject PRs and verify the same-repository resource identity.
Incidental title, labels, assignees and other UI metadata are not semantic inputs.

A logical duplicate is deduplicated only with identical raw bytes/actor. Every
physical occurrence remains indexed. Conflicting duplicates, missing references,
revision gaps/forks and disconnected attempt chains fail closed. Physical IDs
and fetch order never define causal order.

## Lifecycle and close

One current revision derives readiness from its exact relation chain:
BUILDER_READY -> GUARD_REVIEW -> BUILDER_READY (REWORK) or ACCEPTED
(GUARD close-ready) -> CLOSE_OBSERVED (GUARD disposition-ready) -> CLOSED.
A superseded revision is historical; if the next OPEN has not arrived, GUARD
is ready to register the next specification. No generic v1 OPEN readiness is
added. A second candidate requires exact REWORK. ACCEPT never implies physical
closure. Green tests are not acceptance.

For the pilot the issue must have no reopen and at most one close event.
Open state requires no close event; closed state must match close ID actor and
timestamp through current issue metadata. Only GUARD actor closure is admitted.
Exact task ACCEPT material and a physically present immutable ACCEPT control
occurrence must precede the close strictly. CLOSED disposition binds one such
physical occurrence and the exact close event and must follow it strictly.
A late identical logical retry cannot replace the missing bound occurrence.
Without disposition, honest physical close is a recoverable nonterminal state.

The returned integrity ledger covers immutable task identity/body, referenced
material, admitted control occurrences and observed close event. With a retained
ledger, disappearance or modification conflicts. Fresh replay can detect current
digest/ref/chronology violations, not completely erased unobserved history.
Signal and incidental UI state never affect task semantics. The returned facts
index retains physical ref, exact raw digest and event for later delivery
integration. Readiness is coordination information, never execution authority.
