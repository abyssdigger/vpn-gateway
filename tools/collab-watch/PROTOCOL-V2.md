# COLLAB v2 — project Issue work plane, Units 1–3b-1

Status: staged implementation for independent review; not an active epoch.
The v0/v1 modules, protocol, configurations and current journal are unchanged.

## Boundary

This unit implements a pure task registry, material admission and relation reducer.
Unit 2 adds standalone acquisition. Unit 3a adds compact transport. None implements preflight, publishing, Issue
closure, holder-command execution, health/receipt handling or epoch cutover.
Non-task control kinds are rejected by this unit, not silently ignored. Later
units must compose the holder/health/receipt/signal projections without creating
a second task lifecycle. The v1 signal wire may be reused through the physical
fact index.

The input is a trusted, complete normalized observation, not an arbitrary URL
or authority. Acquisition proves bounded completeness and observed stability separately.

## Configuration and discovery

The v2 config uses protocol "vpng-collab/2", repository, journal_rooms (fixed
control Issues), signal_room, journal_epoch, roles, projectholder and
command_registry. The pilot has three distinct roles: SPEC, BUILDER and GUARD.
Their actor IDs may be equal and the same model may carry SPEC and GUARD,
but incarnations must be distinct. Every action selects exactly one active role.
A future v2 role-binding artifact must map a runtime model to one or more explicit
role/incarnation pairs and require the selected pair to be authorized for that
specific action; shared context cannot establish active identity. The transitional
v1 root binding artifact remains unchanged. Role claims are cooperative and not
cryptographic authentication. The runtime role gate and write authority remain
external. A fresh epoch needs an explicitly reviewed clean control surface:
legacy framed events must not silently enter v2 replay.

Only fully structurally validated OPEN control facts from SPEC in a configured
control room discover a task. Task identity is a one-to-one binding of task key,
control room, configured repository, numeric Issue number and immutable Issue ID.
No dynamic Issue numbers in config. Neither prose nor RESULT/REVIEW references
discover tasks. Discovery is bounded and rejects rebindings before acquisition.
Full material admission remains necessary after discovery.

## Exact control wire

A control comment has first line "<!-- vpng-collab-journal/2 -->", then exactly
one fenced json object and no trailing prose. Fields are closed. Every event
carries protocol, journal_epoch, event_id, kind, room, from, to, incarnation,
task, revision. All task relations are single-recipient. OPEN and SUPERSEDED
are SPEC -> BUILDER, RESULT is BUILDER -> GUARD. REVIEW REWORK/ACCEPT and
CLOSED are GUARD -> BUILDER; REVIEW SPEC_REQUIRED is GUARD -> SPEC. SPEC
owns specifications only; BUILDER owns result/evidence; GUARD owns review,
acceptance and closure. None of these role claims grants write authority.

OPEN adds task_ref = {issue_number, issue_id}, spec_ref and previous.
Revision 1: spec_ref = {kind:"issue_body",body_sha256}, previous = null.
Later revisions: spec_ref = {kind:"issue_comment",comment_id,body_sha256},
previous = exact SPEC-owned SUPERSEDED disposition event ID of prior revision.
The immutable r1 Issue body remains bound for all revisions. Later SPEC comments
carry the complete new specification, not a delta or mutable body mirror.
SPEC may supersede an exact current relation head while the Issue remains open,
including before RESULT and after ACCEPT; this invalidates all prior candidates
and acceptance for the superseded revision. A material specification change
still needs an accepted product/project basis outside this protocol.

RESULT adds open_id, previous, attempt, commit_sha, material_ref.
First result cites OPEN; later result cites exact prior REWORK and increments
attempt. REVIEW adds those same fields plus verdict (REWORK, ACCEPT or SPEC_REQUIRED);
previous cites exact RESULT. Its attempt and commit SHA must equal RESULT.
material_ref = {comment_id,body_sha256}, scoped to the registered Issue.

DISPOSITION adds open_id, previous and disposition. SPEC's SUPERSEDED cites the
exact current relation head; a new revision is permitted only after explicit
supersession. In particular, SPEC_REQUIRED hands off to SPEC, which supersedes
that exact review and publishes the next full specification. GUARD's CLOSED
cites the ACCEPT head and adds accept_ref =
{room,comment_id,body_sha256} and close_event = {id,actor_id,created_at}.
accept_ref identifies a physical ACCEPT control occurrence, not just its logical
event ID. No alternative closure or automatic issue mutation exists in pilot.

## Work-plane material

Referenced task comments start with this hidden header (one strict JSON line):

    <!-- vpng-collab-task-material/2
    {"kind":"RESULT","role":"BUILDER","incarnation":"builder-v2","task":"O1","revision":1,"attempt":1,"commit_sha":"<40hex>"}
    -->
    Candidate SHA: <same 40hex>

    Human-readable evidence prose

REVIEW adds verdict to the header and uses visible "GUARD ACCEPT: <sha>",
"GUARD REWORK: <sha>" or "GUARD SPEC_REQUIRED: <sha>" followed by nonempty
substantive prose. SPEC r2+ header has kind SPEC, role SPEC, incarnation, task,
revision, followed by complete specification prose. The exact role and
incarnation of each typed material must match the current configuration and
referencing control owner. All header fields must match the referencing event
exactly. Control records bind
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
history. Initial Issue author must be configured SPEC for this pilot; the
SPEC OPEN supplies the typed role/incarnation claim for the ordinary r1 body.
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
GUARD's SPEC_REQUIRED yields SPEC_REQUIRED state and SPEC readiness, not
implementation rework. A superseded revision is historical; if the next OPEN
has not arrived, SPEC is ready to register the next specification. A task not
yet registered is outside this task reducer, not an implied READY record.
No generic v1 OPEN readiness is added. A second candidate requires exact REWORK.
ACCEPT never implies physical closure. Green tests are not acceptance.
Physical close forbids any further specification revision.

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

## Unit 2 — standalone acquisition

`v2_acquisition.acquire_v2(cfg, token=None, opener=None)` returns `(control, tasks)`
for `project_v2`. It uses fixed GitHub GET endpoints derived from validated repo and
numeric Issue identities. Each complete scan reads fixed control rooms, structurally
discovers tasks, and reads each Issue resource, comments and Issue events. Task
resource repository/number/immutable ID and comment parent URL are checked; PRs
are rejected. Only closed/reopened events are semantic; other events still count
against pagination and resource bounds. Two complete scans must agree, including
task set, comment timestamps, body and closure metadata; incidental UI metadata
and row order are ignored. No arbitrary response URL is followed. Full pages
without Link require an explicit extra page; empty continuation, no progress,
conflicting overlap and page/row/byte exhaustion fail closed. No redirects or
credential forwarding. Public acquisition errors do not include remote strings.
Stable observations do not prove transactional snapshot or unobserved history.
No legacy dispatch, persistence, compact, preflight, holder/signal projection,
write actuator or epoch migration in Unit 2.

For a future multi-role model binding, distinguish runtime identity, allowed role
assignments and one explicit CURRENT_ROLE for each bounded action/unit. A switch
is explicit between units and rechecks the new role/incarnation before its first
action. Evidence from one role is not authority for another. This is a future
operational contract, not a change to current v1 bindings.

## Unit 3a — compact observation transport

`v2_compact.compact_v2(cfg, control, tasks, previous=None)` accepts only trusted,
complete, stable normalized Unit-2 observations. It first projects the full raw
observation, then emits versioned canonical JSON plus exact transfer SHA-256 and
full inventory SHA-256. It must prove exact projection **and retained state**
equivalence against the original reducer before returning. Decoder verifies
canonical bytes, transfer digest, exact full config and dynamic partition identity,
then uses the same reducer. No second lifecycle parser is introduced.

The task envelope (r1 Issue body, identity, lifecycle metadata/events) remains
raw. Control rows from known worker actors beginning the reserved journal family
prefix, and all task comments beginning the task-material family prefix, remain
raw even when not yet referenced or malformed. Ordinary prose becomes opaque:
partition + physical ID + actor + created/updated timestamps + exact body digest.
Validate physical duplicates before omission; identical duplicates deduplicate,
conflicts fail. Opaque rows remain inventory only and are never reconstructed or
promoted into semantic material. The full inventory digest binds the entire
partitioned observation, including opaque additions/removals/changes. Whole-wire
hash additionally binds the exact config; signal-room rotation requires a new
transport encoding even when semantic config is unchanged.

A trusted expected digest binds exact bytes, not acquisition completeness, honest
classification, GitHub provenance or unseen history. The producer is responsible
for the Unit-2 acquisition boundary. No prospective OPEN extension, preflight,
CLI dispatch, publisher, close actuator, live pilot or epoch migration here.

## Unit 3b-1 — existing-task conditional preflight

`v2_preflight` admits exact outgoing control candidate bytes for an already
registered task (RESULT, REVIEW, SUPERSEDED, revision OPEN, and CLOSED), or an
exact Issue-close request. Raw and compact callers share the Unit-3a inventory
binding and the canonical reducer. Shared `inspect_material` and
`advance_relation` helpers preserve the existing replay predicates; preflight
validates the exact current predecessor and prospective registry without adding
any physical row. No synthetic GitHub comment ID, timestamp, close event,
readiness or retained state is returned or admitted.

A conditional control proof binds config/epoch, candidate exact bytes digest,
role/incarnation/actor, current task/head and predecessor physical occurrence,
material/accept/close identities as applicable, baseline semantic state and full
inventory hashes. The future real immutable comment must bind the exact body,
actor, room and logical event ID and have created_at strictly greater than the
applicable physical predecessor/material/close timestamps. Equal seconds do not
prove chronology. An already-observed logical event ID requires reconciliation,
not another preflight/send. Actual admission remains fresh acquired replay.

A conditional close proof requires exact current ACCEPTED open Issue, revision,
attempt/SHA and nominated physical ACCEPT occurrence. It binds exact Issue ID,
GUARD actor and a strict future real close-event time bound; it creates no close
event. CLOSED control proof is possible only after canonical CLOSE_OBSERVED and
must bind exact observed close + eligible physical ACCEPT. Initial new-task OPEN,
prospective acquisition, post-send actuator/retry, CLI, writes and epoch migration
remain out of scope.

Every raw/compact control and close preflight API requires explicit keyword
arguments selected_role and selected_incarnation in addition to physical actor.
They must match the configured role/actor/incarnation, and control candidate
from/incarnation must exactly match the selected binding. Issue close requires
selected GUARD, not merely its possibly shared GitHub actor ID. Proofs retain
this independent CURRENT_ROLE selection. This is cooperative structural checking,
not authentication; runtime model-to-role authorization remains external.
