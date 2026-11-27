# COLLAB v2 — project Issue work plane, Units 1–4a

Status: staged implementation for independent review; not an active epoch.
The v0/v1 modules, protocol, configurations and current journal are unchanged.

## Boundary

This unit implements a pure task registry, material admission and relation reducer.
Unit 2 adds standalone acquisition. Unit 3a adds compact transport. Unit 3b adds conditional preflight; Unit 3c verifies actual post-action
observations. None implements publishing, Issue-close mutation, holder-command
execution, health/receipt handling or epoch cutover.
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

## Unit 3b-2 — prospective initial OPEN

A separate read-only acquire_v2_for_initial_open path parses an exact r1 OPEN
against configured actor and explicit selected SPEC/incarnation before any
candidate-directed network. In each complete scan, validate the baseline control
registry and one exact prospective new task/number/immutable ID before fetching
that numeric Issue through Reader.task. Candidate and extra partition never
enter the baseline task registry/state. Both scans cover the baseline plus
one separate extra Issue under shared bounds; any drift or actual occurrence
of the candidate event requires reconciliation, not a prospective success.

The raw/compact initial-OPEN preflight consumes the baseline and exactly one
already acquired extra task. The Issue must be physically open, same repository,
number and immutable ID, non-PR, configured SPEC author and exact r1 body digest.
The proof binds baseline state/inventory, separate complete normalized extra
observation digest, explicit selected SPEC, candidate exact bytes/ref/spec and
strict eventual real immutable control creation after Issue creation. No
registration/readiness/state advancement before canonical physical admission.
No Issue creation/comment send, post-send actuator, CLI, holder/signal, live
workflow or epoch migration here.


## Unit 3c — actual post-action readback

Pure verify_control, verify_initial_open and verify_close recompute the accepted
conditional preflight from the exact original compact baseline, prior retained
state, selected role/incarnation/actor and exact body/request. Initial OPEN
also requires the separately acquired original extra Issue. Each verifier
requires the independently retained original preflight SHA-256 (canonical
proof). This digest binds the inputs, not authority or external provenance;
no caller-supplied proof fields relax validation.

Fresh complete stable Unit-2 observations must replay canonically with the
full state derived from the original baseline. Existing and initial-OPEN
control verification finds the exact admitted immutable event, actor, room,
body digest and physical occurrence, strictly after its preflight lower bound.
A successful POST response can supply an expected {room,comment_id}; it must
match that exact occurrence even if another matches. Without an expected ref,
exactly one admitted occurrence may reconcile an ambiguous send. Zero or
multiple occurrences remain unresolved; neither permits retry. An exact
expected occurrence may resolve amid identical duplicates; the receipt reports
their count. Later legitimate relations need not leave the verified event at
the current head. Initial OPEN additionally requires the preflight Issue
identity to match the now canonically discovered Issue; ordinary post-preflight
comments may change without changing that identity.

Close verification requires the same task, Issue, revision, attempt, accepted
SHA, original Issue identity, and actual normalized GUARD close event strictly
after the exact nominated physical ACCEPT. Canonical CLOSE_OBSERVED or a later
valid CLOSED disposition may satisfy it. PATCH has no ACCEPT-ref field, so
the later disposition may nominate a different eligible physical duplicate;
the nominated preflight occurrence must still be present and independently
precede the actual close.

Receipts bind the original proof, baseline and post-state digests, explicit
selected role/incarnation and actual physical occurrence or close identity.
They create no ledger, state, synthetic event, retry or mutation authority.
The caller supplies fresh trusted observations; the verifier cannot prove
GitHub provenance or attribute identical actions to a particular HTTP call.
Fresh pre-mutation inventory comparison, HTTP send/PATCH, retry policy, CLI,
live evidence, holder/signal composition and epoch cutover remain outside 3c.


## Unit 3d — task material publication contract

Pure preflight_material accepts an exact compact baseline, task key, physical
actor, explicit selected role/incarnation, candidate bytes and optional retained
state. Canonical replay and parse_header establish the exact current open task,
header and owner. RESULT requires BUILDER_READY at the next attempt/current
revision; REVIEW requires GUARD_REVIEW and the current RESULT's exact revision,
attempt and SHA; SPEC requires SUPERSEDED and the next revision (>1).
Revision-1 specification is the Issue body. A matching already-observed
immutable same-actor body is a reconciliation/reuse conflict, not permission
to publish again; an edited matching body also fails closed.

The conditional proof binds the full config, selected role/incarnation,
actor, task/Issue identity and lifecycle point, exact header and body digest,
baseline retained-state and full inventory hashes. No physical material_ref
is invented. The future exact immutable comment must be in the same Issue
with created_at >= Issue.created_at. Unlike control chronology, equality with
Issue creation is permitted by canonical material admission.

verify_material recomputes the original preflight and requires its independently
retained digest, then canonically replays the fresh complete stable post-read
with the full derived original baseline state. It resolves the exact immutable
actor/body/header occurrence, either by returned physical comment ID or by
unique occurrence if no ID was returned. Zero or multiple exact occurrences
without a locator are unresolved; neither permits retry. It checks the same
Issue identity and the material creation bound. Legitimate later canonical
activity and ordinary comments need not leave the task at its original
lifecycle point. The receipt binds exact material_ref, header, actor, time,
original proof, baseline/post-state and post inventory hashes. Only a later
real control fact referencing this material can make it semantically active.
There is no HTTP write, control publication, retry, or mutation authority.


## Unit 4a — durable noncanonical attempt integrity

An explicitly provisioned SQLite file is a transport-attempt ledger, separate
from canonical task semantics and authority. initialize(path, store_id) creates
a new file only; open_store(path, expected_store_id) requires an existing exact
schema/version and externally pinned store identity. No automatic recovery,
recreation, migration, deletion, reset or rearm. SQLite uses DELETE journal
mode, synchronous=FULL, bounded busy timeout, atomic transactions and a unique
partial effect index. Each decision revalidates schema/store identity and all
bounded stored rows, including canonical descriptor hashes and lifecycle
metadata. The generic storage accepts bounded JSON identity metadata only, not
arbitrary bodies/prose or credential fields; the semantic caller must provide
closed non-secret action/effect schemas and must not hide secrets in IDs.

prepare(action_descriptor, effect_descriptor) records exact canonical metadata,
action_key and effect_key. A new exact proof for the same effect can create
another PREPARED row because no transport was yet attempted. An identical
action/effect prepare is idempotent observation; an action/effect mismatch
conflicts. The atomic PREPARED -> STARTED transition commits before returning
and permits at most one non-PREPARED action for an effect across concurrent
connections and restarts. An effect already STARTED, UNRESOLVED or VERIFIED
can never be started again through a refreshed preflight. STARTED may become
UNRESOLVED or VERIFIED; UNRESOLVED may only become VERIFIED after readback.
VERIFIED binds a receipt digest and optional bounded physical locator.
There is no release or retry transition.

The actuator must use one authoritative persistent store (or a separately
reviewed equivalent), a stable effect descriptor independent of refreshable
proof/inventory evidence, and retain original preflight/readback inputs outside
this metadata-only ledger. Local SQLite cannot coordinate independent stores,
detect an undetected rollback or a deliberately recreated database with the
same externally pinned identity, or prove storage hardware durability; store
identity must never be reused. An ephemeral sandbox is not a durable attempt
backend. Loss, unknown identity, or unavailable storage fails closed and needs
explicit investigation. STARTED only means an external side effect is possible,
not that it happened. Absence after a crash permits read-only reconciliation,
never another send. No HTTP mutation or PRE_MUTATION authority evaluation in
this unit; the next actuator unit owns semantic action/effect schemas.

The read-only claimed(effect_descriptor) lookup revalidates the store and
returns the exact non-PREPARED winner (or None when no attempt has crossed
STARTED). Recovery can find the original action by stable effect even if a
refreshed PREPARED attempt has a different action key. Lookup never grants
permission to retry or changes state.

A separate write-once response_hint is bounded transport identity metadata,
not a verified locator or receipt. record_response_hint is permitted only in
STARTED or UNRESOLVED; identical repeat is idempotent, different hint conflicts.
It survives all later states and claimed-effect lookup. After VERIFIED it
cannot be written. If a crash occurs before durable hint recording, recovery
remains genuinely ambiguous; no retry is permitted. The staged schema is
version 2; no migration of the earlier unaccepted staging schema is provided.


## Unit 4b — staged single-attempt actuator

The staged actuator composes the accepted v2 preflight, complete stable
acquisition, persistent attempt ledger and canonical readback. Exact original
inputs are detached as canonical bytes and retained through a separately
provided durable input store; the generic attempt ledger receives only bounded
identity metadata. The provider contract is not itself a production storage
implementation. No CLI, live activation, new Issue creation or authority
policy is added.

A provisional PREPARED row for a strict operation cannot be started by the
actuator. Fresh identical conditional preflight and deterministic immutable
server-created chronology witness selection qualify an exact second PREPARED
descriptor for the same stable effect. The witness binds room, physical row
identity, created_at and row digest. Material uses the existing non-strict
creation bound and needs no strict witness. A changed inventory/proof or absent
witness fails closed before any send; a refresh before STARTED requires a new
original proof. The witness is eligibility evidence, not a guarantee of the
timestamp of the next write.

Read and write credentials are separate. The actuator independently verifies
the write actor through fixed /user GET, checks external exact-action runtime
authority against a detached descriptor, then durably starts one attempt.
The bounded fixed-target HTTP write is called only after STARTED. A response
locator, if established, is persisted as a hint and must be independently
verified. The canonical Unit-3 verifier is the only success parser. Any
ambiguous send, failure or restart uses read-only remote reconciliation of
the claimed effect and its original inputs; missing evidence never re-arms
the effect. Store uncertainty after STARTED is explicitly not VERIFIED.


### Unit 4b correction — closed transport, request equivalence, single owner

The public actuator accepts no write opener. It constructs its own no-redirect
HTTP transport for both actor verification and the one post-STARTED mutation.
Test-only injection patches private implementation seams; the mutation redirect
test exercises the actual urllib redirect handler without network traffic.

An existing effect claim prevents a second send but is not evidence that the
newly requested action is equivalent. Before returning a claimed receipt or
reconciling it on behalf of a new invocation, compare every closed action
identity field except refreshable proof/input/witness/config digests. Repository
and target path casing is normalized for GitHub identity. Include the full
logical close request digest (including the nominated ACCEPT), not merely
PATCH bytes. Full config identity remains exact-action evidence, not stable
request identity; signal-room rotation alone does not change the requested
mutation. A mismatch returns
EFFECT_CLAIM_CONFLICT with the old action key and zero mutation; compatible
refresh returns the original attempt's key/receipt, not a receipt for the new
proof.

The staged Linux actuator mechanically serializes **all** public invocations
against the existing authoritative SQLite ledger inode using nonblocking
exclusive flock. This covers new attempts, STARTED send, response hint
persistence, readback and reconcile-only recovery. A busy contender returns
ACTUATOR_BUSY before reading or changing attempt state or making HTTP calls.
The lock is held on an existing regular nonsymlink file; no sidecar is created,
and the operating system releases it on descriptor close/process exit.
SQLite's own record locks are independent. Production deployment must use a
single stable local authoritative ledger inode and route all state-mutating
transport operations through this interface; no concurrent direct ledger
mutation, file replacement, fork while held, or independent ledger replica.
These are explicit deployment boundaries, not claims of distributed locking.
The Unit 4a schema and irreversible STARTED semantics are unchanged. A crash
after STARTED still leaves an ambiguous effect for read-only reconciliation,
never another send.


## Unit 4c — durable original-input provider and pairing

A separate explicitly initialized SQLite provider binds its external provider
identity to the authoritative attempt store identity. Runtime open requires
both externally pinned IDs and exact existing schema/version. Initialization
is exclusive and owner-only (0600), commits the schema and syncs the parent
directory entry. Every operation requires an existing regular nonsymlink
owner-only file, DELETE journal, synchronous FULL and bounded busy timeout.
No auto-create, migration, reset, recovery, deletion or GC.

The provider stores immutable exact canonical UTF-8 original input as BLOB,
keyed by the exact actuator action key, with independently computed SHA-256.
Save is insert-or-identical in one committed transaction; a different value
under the same key conflicts. Load revalidates schema, pair, bounds, key,
stored digest and canonical encoding. Per-row limit matches the actuator
original-input bound (128 MiB); total 512 MiB and at most 10,000 rows. A
capacity failure stops new sends, never deletes prior evidence. The provider
does not replay or interpret task semantics; the actuator still recomputes
the exact action/effect/proof binding. Originals contain potentially
confidential material and remain outside the metadata-only attempt ledger;
diagnostics never include original bytes or arbitrary exception strings.

The public actuator now requires the concrete InputStore type, not an
arbitrary save/load callback. Under existing Unit-4b ownership it validates
the provider pair before any new preparation or claimed reconciliation,
commits and reloads exact input before STARTED, and revalidates pair and
input immediately before the irreversible transition. Recovery reopens
the exact claimed input and recomputes its proof and descriptor, including
before returning an existing VERIFIED receipt. Missing or corrupted original
or unavailable pair for a claimed effect yields EFFECT_UNKNOWN and no resend.
Failure before STARTED creates no effect claim. A committed input before
STARTED may remain as an immutable orphan; it is not authorization or a
transport attempt and an identical later eligible preparation may reuse it.

Trusted deployment must pin both identities outside the two files, use one
stable local pair and an owner-controlled directory, prevent identity reuse,
replacement and rollback, and treat backups as sensitive. Two SQLite files
are not distributed atomicity or hostile-storage protection. No live/CLI
activation or new write authority is introduced.


An opened provider also pins its physical DB identity (device and inode) with
a live Linux O_PATH close-on-exec nonsymlink inode handle for the lifetime of
the provider object. Each transaction checks the pathname against the held
inode and validates owner/mode/type before opening and again around the
transaction. Retaining the descriptor prevents inode-number reuse while the
old handle exists. Explicit close invalidates the handle. Provisioning retains
an O_PATH pin of its exclusive-created inode through the validated open,
closing the ordinary provisioning descriptor before SQLite operations. O_PATH
close preserves POSIX record locks held on the same inode by SQLite in the
process; an ordinary read-only descriptor would release them. An already opened
provider therefore rejects even a same-logical-ID replacement. A fresh
explicit open cannot establish historical inode continuity by itself; this
does not solve concurrent hostile path substitution or rollback, and the
external no-reuse/no-replacement trust boundary remains.


Immediately after successful canonical remote readback, and before persisting
VERIFIED, the actuator revalidates the provider pair and reloads the exact
claimed input. Byte equality to the already recomputed bound original
confirms the same action/effect identity; missing, replaced or changed input
yields EFFECT_UNKNOWN without persisting a verification receipt. This is a
last local check, not atomic coordination of two files against hostile
concurrent replacement.


## Unit 4d — single-attempt project-task Issue creation

A creation effect is scoped to normalized repository, exact journal epoch
and logical task key. A PREPARED but unstarted action may refresh title/spec;
after STARTED, different intent conflicts. Migration of a task across epochs
requires a separate identity contract. The selected SPEC, incarnation, actor,
configured journal room, r1 request and exact generated title/body are bound.
No physical Issue identity is invented by prospective preflight.

The hidden creation marker begins with `<!-- vpng-collab-task-create/2`,
then one canonical bounded JSON line, a closing `-->`, a blank line and
the exact human specification. It binds repository/epoch/task/r1/room,
role/incarnation/actor, human title/spec digests and effect digest. The
complete generated body digest, including the marker, is the r1 OPEN
specification digest. Reserved creation-marker injection is rejected.

Separate read-only creation inventory uses the fixed repository Issues
endpoint, state=all, created ascending, 100 rows per page, fixed numeric
pagination and the established page/row/byte ceilings. PRs count toward
bounds. Two complete normalized scans must agree; malformed reserved markers,
foreign resources, conflicting physical ID/number, no progress, incomplete
pages or unstable inventory fail closed. Before STARTED require zero matching
markers. After STARTED require exactly one matching non-PR marker and an
equal fixed numeric Issue GET. Even a response hint cannot bypass unique
inventory verification. No search-index text or response URL is followed.

The existing closed actuator retains exact inputs, validates the actor and
authority and the provider pair, durably STARTs before exactly one POST,
records optional numeric Issue identity as hint, then verifies physical
readback with canonical task replay and final retained-input check. Loss of
response, zero or multiple markers, wrong hint, or readback failure cannot
rearm. Creation receipt is not registration: later initial OPEN is separate
and binds the complete generated body digest. An already observed exact r1
OPEN may corroborate readback; a conflicting binding cannot.

The marker is cooperative immutable-by-contract, not proof of unobserved
GitHub edit history. No distributed atomicity, hostile rollback protection,
external racing creator guarantee, live activation, CLI, epoch cutover or
main publication is established.


## Unit 5a — pure auxiliary projection

The auxiliary family uses the exact marker `<!-- vpng-collab-aux/2 -->`
and protocol `vpng-collab-aux/2`, followed by the existing strict JSON frame.
Only HANDLED, PING and PONG are admitted. Common fields are protocol, epoch
(journal_epoch), event_id, kind, room, from, to and incarnation. HANDLED adds
only handled (1–100 unique physical receipt targets); PING adds only ping_id
(equal to event_id); PONG adds only ping_id, ping_ref and ping_sha256.
No payload, task lifecycle, authority or client-clock fields are admitted.
Sender actor/incarnation, exact configured physical room, recipient and
reserved namespaces are checked. Logical IDs are disjoint from task and
holder IDs. Identical logical duplicates retain distinct physical facts.

`project_aux` invokes the accepted `project_v2` with the same complete
control observation, without filtering or modifying the task result/state.
It admits exact configured holder rows, classifies via the closed registry,
and exposes independent role mailboxes. A holder command is only classified
and routed, never executed or evaluated for authority. The auxiliary ledger
binds full normalized physical holder/aux rows (including timestamps, actor
and body); aux rows must be unedited. Retained replay rejects changed/missing
rows and config changes. The semantic config identity excludes signal room;
task and aux retained state are separate typed components.

HANDLED is self-addressed and resolves exact logical ID, physical ref, raw
body digest and recipient across holder, task and aux facts; HANDLED is
never a receipt target. Only holder mailbox readiness is cleared. PONG
reverses the exact referenced physical PING in the same room, with matching
digest and logical ID. The health projection is per physical PING occurrence,
not an elapsed timer, inferred liveness, or scheduling policy.

Existing signal/1 wire resolves only task and aux facts other than HANDLED.
Signal observation, quarantine and GC-candidate evidence remain noncanonical;
only exact recipient receipts authorize eligibility evidence, never deletion.
Signal disappearance or rotation does not alter the canonical ledger.
Task projection/roles, holder mailbox, delivery, health, signal diagnostics
and GC are separately visible. No acquisition, actuator, CLI, command execution,
live activation, epoch migration, or main publication is introduced.


## Unit 5b — aggregate read and compact transport

`acquire_aggregate_v2` returns a typed four-part `AggregateV2` observation:
control, tasks, holder_rows, signal_rows. One existing bounded Reader acquires
control, discovers task Issues from that same control observation, reads all
tasks, then reads holder and signal comments. A second fresh Reader repeats
the entire pass. Only equal complete normalized graph observations are returned.
All read endpoints, identity checks, redirect policy, pagination and aggregate
per-pass byte/row budgets remain those of the accepted Reader. This is a
stable-observation contract, not an atomic GitHub snapshot. Signal churn can
fail acquisition; it does not change canonical retained state.

The distinct `CompactAggregateV2` wire
`vpng-collab-aggregate-compact-observation/2` binds the full transport config
and all physical inventory partitions. Raw control retention includes both
reserved task/aux families from known workers; task material retention is
unchanged; all configured-holder actor rows and all signal-room rows are raw.
The latter includes quarantined/ignored signal observations. Other comments
may be opaque, binding physical ID, actor, timestamps and raw-body digest.
Normalized acquisition rejects inconsistent physical overlaps before packing.
The compact decoder rejects opaque configured-holder and signal rows.
`compact_aggregate_v2` requires exact complete raw/compact `project_aux`
projection and retained-state equality, including with prior retained state.
`decode_compact_aggregate_v2` admits trusted exact transferred bytes and
replays the same projector; digests do not prove honest classification or
GitHub provenance. Signal rotation changes transport config binding but not
the semantic retained config. Existing task-only acquisition, initial-OPEN
and CompactV2 wire/type/API remain compatible and separate. No outgoing
actuation, scheduler, authority evaluation, CLI, live cutover or main change.


## Unit 5c — auxiliary outgoing proof and single-attempt transport

Auxiliary HANDLED/PING/PONG and optional SIGNAL publication use the existing
actuator with distinct action operations `aux_comment` and `signal_comment`.
The frozen original uses the accepted aggregate compact baseline, prior
composed retained state, explicit selected role/incarnation, exact body and
preflight digest. Conditional proof binds full config, full aggregate
inventory, baseline composed state, candidate bytes and exact admitted targets.
The accepted aux event/relations and signal validators are reused; the internal
nonphysical prospective relation key is never a GitHub ref, target, state,
receipt or returned identity. No synthetic comment ID or task lifecycle exists.

Canonical aux effect identity is **exactly** the existing task-control
namespace: operation=control_comment, normalized repository, epoch, event_id.
SIGNAL uses separate operation=signal_comment, normalized repository, epoch,
signal_id. Request and target intent remain in the exact action; conflicting
intent cannot claim a second STARTED effect.

The same accepted concrete AttemptStore, InputStore, ownership flock,
PREPARED/fresh proof/retention/actor/authority/STARTED sequence, closed
production transport and readback-only reconciliation serve both families.
Aux and SIGNAL POSTs target only validated configured rooms. Full aggregate
fresh proof must match exactly before STARTED. Readback replays the original
proof and baseline, then the fresh aggregate observation using original
composed state. Exact admitted bytes/actor/identity/ref (or unique occurrence
without response hint) are required; disappearance/ambiguity of SIGNAL is
UNRESOLVED, never resend. No signal history becomes canonical; stable unrelated
signal churn does not invalidate canonical aux readback. A verified historical
receipt is not a claim that an ephemeral SIGNAL still exists.

**Staged compatibility limit:** old task-only CompactV2 and task actuator
contracts remain unchanged. Their task-only preflight cannot observe an aux
occurrence externally published outside the shared local attempt store. Shared
effect identity prevents two STARTED claims in one authoritative store, not
independent external writers or a lost store. Before any mixed-family live v2
activation, runtime/scheduler composition must require aggregate task+aux
admission before any new role-attributed task or aux control send. The staged
task-only path is not a mixed-family-safe live scheduler contract.

No holder prose write, command execution, scheduler/clock policy, CLI,
identity migration, epoch cutover, live activation or main publication.


## Unit 6a-A — staged multi-role identity model

The proposed root capability schema `vpng-collab-role-bindings/2` has a
closed bindings list. Each model row has exact model identity, admission
status (admitted or disabled), nonempty allowed transport pairs
(`transport_role`, `incarnation`), and separate process responsibilities
keyed by the transport role that carries them. The pilot transport role
set is SPEC/GUARD/BUILDER; SPEC/ARCHITECTURE additional responsibilities
are not transport pairs or terminal GUARD acceptance authority. All model
rows, including disabled ones, are validated. Duplicate models, duplicate
pairs, duplicate per-model roles or incarnation reuse fail closed.

`select_identity` takes the parsed capability document, independently
established exact runtime model, active role map (actor_id + incarnation)
and optional explicit selected transport role. It intersects admitted
pairs with the active config; a specified role must match exactly, and
without explicit role selection exactly one pair must remain. It returns
only model/transport_role/incarnation. Each role switch requires a fresh
explicit selection and validation. Recovered context, inferred task role,
or caller-supplied incarnation cannot select/override the pair. The
module is pure and does not authenticate the provenance of its inputs,
evaluate authority, establish live-session ownership or execute anything.

The staged fixture preserves existing BUILDER and GUARD identities, adds
a distinct future SPEC incarnation for the GUARD model and preserves its
separate v1 SPEC responsibility. The active v1 role map still selects
GUARD uniquely; the proposed v2 role map requires an explicit GUARD/SPEC
choice. This unit validates a proposed schema only. Root installation and
governing identity-gate replacement remain separately gated in 6a-B;
active v1 config/epoch and root binding are not changed by 6a-A.

Identity selection does not establish session uniqueness or exclusive
transport ownership. Two sessions could select the same allowed pair.
Before live automated writes, 6b must establish the trusted ownership
and fencing boundary. No live activation, migration or authority follows.


## Unit 6b-A — durable local owner capability and exclusion primitive

One explicitly provisioned owner SQLite store binds store ID, normalized
repository and journal epoch. Its closed schema contains only metadata and
role slots: exact role, fixed incarnation, positive generation and SHA-256
capability digest. First claim is generation 1; explicit replacement
requires the exact current generation, increments it by one and cannot
change incarnation. No expiry, clock, heartbeat, recovery/reset, deletion
or automatic takeover exists. The external operator/transition authority
callback must grant the exact detached nonsecret claim/replacement
descriptor; only exact True without descriptor changes permits transition.
An opaque server-generated 256-bit token is returned only in the capability
and not persisted; status and capability repr omit secrets. Losing the
token requires explicit authorized replacement.

Exclusive nonblocking inode flock covers each claim/replacement transaction
and the fence context. The fence validates the complete pinned store and
capability including constant-time digest comparison, closes SQLite before
yielding, and retains the same flock until caller exit. Concurrent owner
replacement returns OWNER_BUSY; only a fresh retry may replace after fence
release. Old capability cannot fence after replacement. No authority or
transport action follows merely from a valid capability.

Explicit O_EXCL owner-only provisioning, directory fsync, SQLite FULL/delete
durability, bounded busy timeout and exact schema/version/meta checks apply.
An O_PATH pin prevents live inode reuse; each operation checks regular
owner-only nonsymlink single-link identity and bounded file size. Runtime
open is existing-only. A fresh reopen cannot detect historical replacement
or rollback; externally pinned one-store continuity and trusted local
storage are required. This is not distributed or hostile-storage fencing.

6b-B must hold this fence over the entire accepted actuator invocation,
with owner-store then attempt-store lock ordering, including readback and
reconciliation. Generation is not part of semantic effect identity.
6b-A makes no actuator, network, GitHub, CLI, config, role selection or
live activation change. A future trusted writer must exclusively control
role-attributed credentials; direct agent writers otherwise bypass the
fence. No credential custody or deployment claim is established.


## Unit 6b-B — owner-fenced actuator composition

The staged actuate_fenced wrapper purely recomputes the exact frozen action
using the accepted binder. It requires its normalized repository, epoch,
selected role and incarnation to equal the concrete capability scope.
Malformed input and owner rejection stop before attempt/input/credential
or remote access. OwnerStore.fence verifies store identity, generation and
token; the wrapper retains it across the unchanged accepted actuator,
including the attempt-store flock, fresh proof, authority, STARTED, send,
hint, readback and reconcile-only paths. Lock ordering is owner then
attempt. Owner BUSY and accepted actuator BUSY are distinct; accepted
results are otherwise passed through unchanged. Unexpected exceptions
after fence entry are conservatively EFFECT_UNKNOWN; BaseException
unwinds both locks without converting a possible send into no-attempt.

Ownership is a runtime prerequisite, not semantic action/effect identity:
generation, token and token digest never enter frozen originals,
authority descriptors, attempt/input stores, receipts or GitHub wire.
Replacement with the same role/incarnation can reconcile a prior STARTED
or UNRESOLVED effect, never resend. The stale capability cannot invoke even
reconciliation. The wrapper does not claim or replace an owner.

Tests use accepted task/aux actuator paths with synthetic transport,
including takeover exclusion during real send/readback logic, stale owner,
authority denial, attempt-store contention and crash/recovery. This does
not convert the staged task-only path into an aggregate-safe runtime
contract. A live writer still requires mandatory aggregate admission,
externally pinned one-store continuity, sole write-credential custody and
routing every role-attributed mutation through this wrapper. Direct
credential bypass is not prevented by local fencing. No runtime/CLI,
scheduler, deployment, config/epoch migration or main publication occurs.


## Unit 7a — pure selected-role scheduler projection

project_scheduler receives a validated staged config, accepted normalized
four-part aggregate, exact previous composed state, parsed binding document,
independent runtime model and optional explicit role. It invokes the
accepted identity selector and exactly one project_aux replay. The returned
composed state is exactly the accepted state; no second reducer or derived
scheduler fields enter it.

The closed selected-role view separates task readiness reasons and holder
mailbox/input facts (work) from incoming/outgoing PING occurrence evidence
(health), admitted incoming SIGNAL diagnostics, unconsumed physical refs
and GC eligibility evidence addressed to the selected role. Valid SIGNAL
exposure is recipient-only; no outgoing attribution is inferred.
Quarantined signals have no admitted semantic recipient. Conflict and
ignored-external observations are copied into separate global/unattributed
transport diagnostics, never role-attributed even when multiple roles share
a physical actor. No malformed payload is parsed to infer role or work. GC evidence is
not delete authority. Holder command classification is data, never executed.
No health/delivery/GC observation can clear or change task/holder work.

A WAITING role with an empty mailbox is not semantic STOP or dormancy proof.
No clock, timer, failure verdict, persistence, network, model invocation,
mutation, authority evaluation, legacy projector, CLI, live activation,
root binding installation or epoch cutover occurs here. The external
runtime must acquire the aggregate and persist the exact canonical state.


## Unit 7b-A — durable composed-state checkpoint

An explicitly provisioned local SQLite store binds state-store ID, normalized
repository and exact journal epoch. It holds one optional checkpoint:
generation, canonical UTF-8 composed retained state bytes and SHA-256.
The closed storage shape is exactly task/aux, each with accepted protocol,
semantic config hash and digest ledger; the two config identities match.
The store checks shape/encoding, not semantic provenance or completeness.
A caller must obtain the state from the accepted projector.

The first save requires generation zero; later saves are atomic CAS against
the exact current generation, incrementing even for byte-identical state.
Stale/overflow saves fail closed. Load validates schema, metadata, byte
bounds, digest, strict canonical decoding and closed shape; returned state
is detached. Byte limit 32 MiB. O_EXCL/0600/single-link/nonsymlink provision,
directory fsync, FULL/DELETE SQLite, bounded busy timeout, existing-only
open and live O_PATH inode pin follow accepted store conventions. A fresh
open cannot prove historical continuity after hostile replacement or
rollback; external no-reuse/no-rollback remains mandatory.

The store adds no projection, work view, holder prose, signal history, role,
clock/timer, authority, owner capability or credential fields. A checkpoint
save is local evidence, not work acknowledgement or semantic progression.
Missing store/checkpoint permits only explicit fresh-current reconstruction
with no historical continuity claim. No acquisition/scheduler orchestration,
actuator, model invocation, CLI, remote mutation, activation or epoch change.
7b-B must bind checkpoint load/save to accepted aggregate replay.


## Unit 7b-B — bounded one-shot runtime read/checkpoint commit

run_once binds an already-open exact RuntimeStateStore to the staged
config repository/epoch. The caller supplies the parsed binding document,
independent runtime model, optional explicit role, read credential/opener
and explicit retained or fresh-current history mode. Retained requires
an existing checkpoint; fresh-current requires an empty provisioned store
and labels its result fresh-current-only. No fallback or reset.

The sequence is load once, accepted two-pass aggregate acquisition,
accepted selected-role scheduler with exact previous state or None, then
save the exact returned canonical state using the loaded generation CAS.
Only after successful save is the view returned with committed generation
and state digest. No checkpoint DB transaction spans network reads.
Acquisition/identity/replay conflict or failed/uncertain CAS yields no
authoritative view/commit claim. A competing commit requires a new load
and acquisition; no silent retry. Signal churn remains noncanonical.
Retained mode does not prove historical continuity beyond externally
pinned checkpoint trust. Results exclude raw checkpoint bytes/credentials.
Holder commands remain data. No remote writes, actuator, owner change,
command execution, model invocation, timer, CLI, daemon or activation.


## Unit 7c-A — admitted peer journal inventory

The selected-role view includes `peer_journal_inventory`, keyed by every
configured transport role except the selected role (including empty buckets).
Each bucket contains admitted physical task and auxiliary journal occurrences
from the single composed projection, sorted lexically by physical_ref. Each row
has exactly physical_ref, event_id, kind, sender, to (the admitted recipient
list), and body_sha256. Distinct physical occurrences of the same logical event
remain distinct. The role is the admitted event sender, not its GitHub actor.

The inventory includes every admitted kind, including HANDLED/PING/PONG, but
never SIGNAL, holder inputs, task material/prose, raw body, actor ID, or remote
timestamps. It is observation evidence only and changes neither work/health
semantics nor canonical retained state. Physical duplicate evidence can change
the integrity ledger without adding a semantic obligation.

No delta baseline, elapsed clock, timer, pending-PING adoption, health intent,
authority evaluation, network access, persistence or mutation is introduced.
Those runtime policies remain separate from this pure view extension.


## Unit 7c-B — ephemeral communication-health policy

advance_health(view, previous, now_ms) is pure, accepts the admitted selected
role view, and returns detached local state and deterministic intent list.
State binds selected role/incarnation, peer set and last nonnegative integer
monotonic time. For each peer retain content-bound physical peer refs and
outgoing PING ref/ID/digest, local baseline, mode and exact current/ambiguous
episode references. Changed/disappeared retained evidence, identity drift or
backwards time fails closed. Observation order is irrelevant.

Fresh state baselines all existing evidence without reconstructing age. A
single pending outgoing PING adopts a fresh 5m response window; multiple
pending PINGs emit one ambiguous intent; matched PINGs do not start a window.
Any newly observed peer journal occurrence takes precedence over new PINGs
and deadlines, resets to IDLE and marks all outgoing evidence seen. Thus old
durably pending PINGs locally satisfied by another valid peer fact do not
prevent a new PING_DUE after a subsequent full 10m silence. No canonical PONG
is fabricated. Ambiguity covers competing current-episode PING refs (all
pending on restart); previously locally satisfied refs do not rearm.

At >= 10m IDLE emits one PING_DUE(peer) and latches. Only an exact newly
admitted pending outgoing PING starts a fresh 5m response window. Concurrent
new pending PINGs or a second during WAITING_RESPONSE emit one
HEALTH_EPISODE_AMBIGUOUS(peer, sorted ping_refs); new pending PINGs in
UNCONFIRMED/AMBIGUOUS without new peer evidence fail closed. At >= 5m without
peer evidence emit one COMMUNICATION_UNCONFIRMED(peer, ping_id, ping_ref);
latch until new peer evidence. Equal monotonic observations are allowed.
No SIGNAL/holder/task-work/actor/timestamp input participates.

Intents are observation/control requests only, never PING publication,
transport retry, authority, STOP or semantic work/disposition. No clock,
network, persistence, model, command evaluation or checkpoint integration.
The independent 2m peer wait budget remains a separate unit.


## Unit 7c-C — one bounded peer-wait attempt

advance_peer_wait(descriptor, previous, now_ms) accepts exactly role,
incarnation, peer, dependency_key and wait_token, all bounded identifiers;
peer differs from role. None explicitly begins a fresh attempt at the
caller-supplied nonnegative integer monotonic time. Subsequent calls bind
the exact descriptor and nondecreasing time. At >=120000ms it emits exactly
one PEER_WAIT_BUDGET_EXPIRED with the exact descriptor and latches expiry.
Same-now/later calls do not repeat. A later bounded wait for the same
unresolved dependency uses a new token and explicit fresh state after
EXEC_NEXT. Elapsed age is not reconstructed after restart.

Expiry returns scheduler control to EXEC_NEXT only. It does not resolve,
cancel or close the dependency, mark peer communication failure, authorize
a role action, waive independent review or establish STOP. No health state,
journal/projection, clock, sleep, I/O, persistence, checkpoint or actuator
participates. The outer runtime owns actual waiting, exact semantic relation
satisfaction, scheduling and lifecycle transitions.


### Unit 7c-B.1 — prior ephemeral health-state invariant

Non-None previous health state is validated as the exact closed in-memory
shape before use. Role/incarnation and peer set bind the current view;
physical refs/digests and outgoing (ping_id, digest) tuples are checked.
Local times must be ordered nonnegative integers, episode fields must
match the mode and bind retained PING evidence, and ambiguous refs must
be sorted unique tuples. Overdue unlatched or prematurely unconfirmed
episodes fail closed. This structural validation neither authenticates
arbitrary caller state nor changes accepted 10m/5m transitions; the
runtime must retain its own state. No persistence or new semantic reducer.


## Unit 8a — pure aggregate-safe canonical candidate gate

derive_task_compact validates the exact aggregate compact type, text, digest,
inventory and admitted semantic replay before transforming its canonical wire.
Task envelopes and existing opaque rows are preserved; aux raw control rows
become exactly the task-opaque digest rows for the same physical metadata,
using the accepted task retention classifier. Holder/signal partitions are
omitted. The derived task compact is admitted by the existing decoder.
It is byte/inventory-equivalent to task compaction of the same raw graph.

gate_aggregate_candidate is retained-only: the exact closed composed previous
state is mandatory. For control_comment the frozen previous must equal its
task partition; for aux_comment it must equal the whole prior. Complete
aggregate replay, exact derived task compact where applicable, accepted
family-specific preflight with exact expected proof SHA and global task+aux
logical ID absence all must succeed. Selected role/incarnation must match
the admitted proof. No fresh-history fallback or new event grammar.

The closed detached result binds aggregate text/inventory digests, separate
prior and projected composed-state digests, task compact digests where
applicable, exact proof digest, candidate event ID and selected role/incarnation.
It is conditional evidence only, not authority. It contains no raw candidate,
owner/credential/timer or mutation decision. Task and aux canonical comments
are the only admitted operations; SIGNAL/material/close/create/initial OPEN
remain separate. No acquisition, store or actuator behavior. 8b must integrate
the exact gate under owner/attempt fencing with checkpoint revalidation
before STARTED; 8a alone protects no live send.


### Unit 8b-A — checkpoint stability fence

RuntimeStateStore.fence(expected_generation, expected_state_sha256) uses the
same validated BEGIN IMMEDIATE transaction and pinned identity as load/save.
An exact existing checkpoint is mandatory. It yields only generation and
state digest, retains the transaction through the context body and revalidates
physical identity on exit. It never changes the checkpoint or generation.
Competing checkpoint saves cannot commit while the transaction is held;
the existing bounded busy policy applies. Caller exceptions unwind the
transaction; missing, stale, invalid or replaced stores fail closed.

The later writer must acquire locks in owner -> attempt -> checkpoint order.
The checkpoint fence covers final validation through durable STARTED only;
no network acquisition or send may occur inside it. Failure after STARTED
cannot restore send eligibility. Checkpoint generation/digest are freshness
evidence, not effect identity. This unit alone performs no STARTED or
actuator behavior and protects no live send.


### Unit 8b-B — canonical control send admission

New control_comment and aux_comment effects require an exact concrete
RuntimeStateStore checkpoint. Claimed effects remain reconciliation-only
regardless of checkpoint availability. Frozen family previous must match
the exact checkpoint task partition or composed state; no fresh fallback.
Frozen witness and durable original precede actor/authority checks.
One final complete aggregate acquisition and 8a gate admit the candidate;
task witness is reconstructed from that same wire. Owner -> attempt ->
checkpoint lock order holds checkpoint stable across retained-input
revalidation and durable STARTED. Only clean fence exit permits one send.
Pre-STARTED failure cannot send; uncertainty after possible STARTED is
EFFECT_UNKNOWN with no send, and durable claims remain recovery-only.
Checkpoint generation/digest do not enter effect/action/authority/wire or
receipt identity. Other mutation families remain staged, not aggregate-safe.
Trusted credential custody, remaining runtime and live/cutover gates apply.



### Unit 8c-A — coherent prospective initial-OPEN acquisition

acquire_aggregate_v2_for_initial_open validates the exact initial OPEN
candidate through the accepted parser before any network read. Each of two
whole passes uses one Reader and one row/byte budget in the following order:
control comments, registered-task discovery and prospective registry check
from that control snapshot, registered Issue resources/comments/events,
projectholder comments, signal comments, prospective candidate Issue
resource/comments/events. The candidate is returned only in extra_task,
never inserted into the admitted task map.

InitialOpenAggregateV2 is the closed five-part observation
(control, tasks, holder_rows, signal_rows, extra_task). Both passes must be
canonically equal. Already-admitted/alias candidates, inaccessible or invalid
resources, drift in any normalized partition and exhausted shared bounds
fail closed; no independently stabilized aggregate/candidate or legacy
fallback is allowed. This is read-only bounded observation, not atomic remote
snapshot, replay, proof, authority, checkpoint or actuator admission. 8c-B
must perform the pure gate over this exact coherent object and retained
composed frontier; actuator integration remains separate.


### Unit 8c-B — retained-only initial-OPEN aggregate gate

`gate_initial_open_aggregate` requires the exact `InitialOpenAggregateV2`
observation and closed retained composed state. Frozen task history must
canonically match its task partition. The gate compacts the aggregate
partitions once against that retained state, projects them, derives the task
compact from the same wire and invokes accepted initial-OPEN preflight with
the exact prospective extra partition. The frozen proof digest must match;
the candidate logical ID must be absent from both task and aux facts.

The closed conditional result binds aggregate and task compact/inventory
digests, normalized extra-observation digest, distinct prior/projected
composed-state digests, exact proof digest, event ID and selected role/
incarnation. It exposes no raw prose or authorization. Holder or signal
churn may affect aggregate identity without changing the task proof.
Exact observation type prevents accidental split-API composition but does
not authenticate provenance or establish remote atomicity. The trusted
caller must supply the real coherent observation. No acquisition, storage,
timer, actuator, STARTED, send, or live activation is performed.


### Unit 8c-C — initial-OPEN aggregate-safe new send

New initial OPEN effects use the same owner -> attempt -> checkpoint
lock order as canonical control sends. The retained frontier is task-scoped;
the original CompactV2 + extra_task input, canonical control effect namespace
and stable action/request/receipt identities are unchanged. Claimed effects
remain reconciliation-only before any checkpoint or fresh eligibility checks.

The frozen chronology witness and durable original precede actor/authority.
A single final coherent prospective acquisition supplies the accepted 8c-B
gate. Local compaction/derivation from that same graph verifies aggregate/task
digests and reconstructs the exact final witness with its extra_task. There is
no task-only or separately stabilized candidate pre-send scan. Checkpoint
generation/digest are runtime freshness, never action identity. The fence
covers retained-input validation through durable STARTED, exits before the
single physical send, and any possible STARTED uncertainty remains
reconciliation-only. Other mutation families and live/cutover/credential
custody remain separate.


### Unit 8d-A — retained task-state aggregate gate

`gate_task_state_aggregate` accepts only material_comment (task key and
body) or issue_close (close request) with the exact CompactAggregateV2
and closed retained composed frontier. Frozen task history equals its
task partition. Exact aggregate projection and derived task compact feed
the accepted family preflight; recomputed proof and role/incarnation must
match. No candidate journal event ID exists for these physical effects.

The closed conditional result binds aggregate/task compact and inventory,
prior/projected composed state, proof and operation/selection, without
material/request prose or authority. Holder/signal churn may change
aggregate identity without changing the task proof; task, opaque and aux
inventory changes remain bound. No acquisition, persistence, clock,
actuator, STARTED or send is performed.


### Unit 8d-B — aggregate-safe material and close new sends

New material_comment and issue_close effects use task-scoped retained
checkpoint matching and the existing owner/attempt/checkpoint chain.
Their frozen task CompactV2, effect/action/request and receipt identities
remain unchanged. Claimed effects still reconcile before fresh eligibility.

After frozen witness and durable input, actor/authority and input
revalidation precede one final aggregate acquisition. The 8d-A gate
consumes the exact compact; derived task/inventory and aggregate/proof
bindings are checked and the witness is reconstructed from that same
task compact. Material has not_applicable witness; close preserves its
deterministic chronology. No task-only pre-send acquisition or invented
global journal event ID. Checkpoint fence holds through durable STARTED
and releases before one POST/PATCH. Possible STARTED uncertainty sends
nothing and remains reconciliation-only. Existing readback is unchanged.


### Unit 8e-A — coherent creation aggregate acquisition

`acquire_aggregate_v2_for_creation` observes the exact normalized
`CreationAggregateV2(control, tasks, holder_rows, signal_rows, inventory)`
twice. Each complete pass uses one CreationReader and shared row/byte
counters: all journal partitions, discovered registered resources/comments/
events, holder and signal comments, then the full repository Issue inventory
via the existing fixed endpoint and marker validation. The complete
observations must match canonically; no separately stabilized subviews,
candidate fixed-resource read, or inventory filtering is allowed.
Valid creation markers including PR markers are retained, not admitted or
rejected on candidate-effect identity. Invalid identities/markers, unstable
observations or exhausted bounds fail closed. This is bounded read-only
observation, not atomic remote snapshot, proof, policy, authority, store,
actuator or mutation. The later pure gate owns candidate absence.


### Unit 8e-B — pure retained creation aggregate gate

`gate_creation_aggregate` requires the exact CreationAggregateV2 and
closed retained composed state; frozen task history must equal the task
partition. Compact the graph once, project against retained history,
derive task compact from that same wire and recompute the accepted creation
preflight/proof and SPEC selection. Validate the entire normalized inventory
in its 8e-A ascending-ID order with unique IDs/numbers, closed row shapes
and accepted marker validation. Any matching creation-effect marker,
including PR or multiple matches, rejects. Unrelated valid markers and
unmarked rows remain bound by the whole inventory digest. No row filtering.
The detached conditional result binds aggregate/task digests, creation
inventory digest, prior/projected state, proof/effect digests and selection.
No raw request/payload, authority, acquisition, clock, persistence, actuator
or STARTED. Exact observation type is not provenance authentication.


### Unit 8e-C — aggregate-safe new creation send

New issue_create uses the task-scoped retained checkpoint and existing
owner -> attempt -> checkpoint ordering. The frozen witness remains
not_applicable; stable effect/action/input/request/receipt identity is
unchanged. After actor and authority checks and retained input validation,
one coherent creation acquisition supplies the accepted pure gate. Bind
aggregate/task digests and inventories, creation-inventory digest, exact
proof/effect and prior checkpoint digest back to the same observation.
No task-only or separate expect-absent pre-send read remains. Hold the
checkpoint fence through durable STARTED, release before one POST, and
never send on ambiguous STARTED or fence exit. Claimed effects bypass
new admission and retain the existing unique-marker plus fixed-resource
reconciliation without requiring a current checkpoint. No live activation.


### 9a — staged trusted writer data interface

TrustedWriter is constructed by trusted bootstrap, not by the worker. Bootstrap
validates and detaches the exact full canonical v2 configuration and root
bindings, selects identity using the actual runtime model and explicit role
when needed, and pins the repository/epoch, selected role/incarnation/actor,
concrete owner store and capability, attempt store and paired retained-input
store, authority callable, read/write credentials and read transport. The
checkpoint store is concrete and scope-matched when available; explicit
trusted None preserves claimed recovery after checkpoint loss. A missing
write credential is also allowed at bootstrap. No bootstrap current-generation
or claim lookup substitutes for the accepted owner and attempt fences.

The closed data interface invoke(request) accepts exactly an ordinary dict
with original (an exact str containing bounded canonical frozen JSON with the
existing exact field set) and reconcile_only (an exact bool). Full canonical
configuration including signal room, actor, selected role and incarnation must
match the pin. The six new-send families are material_comment, control_comment,
aux_comment, initial_open, issue_close and issue_create. SIGNAL is admitted only
with reconcile_only true for historical recovery, never as a new send. Invalid
ingress returns NO_ATTEMPT/TRUSTED_INGRESS_REJECTED with null action_key before
delegation, I/O or preparation. Valid ingress delegates exactly once to
actuate_fenced: full proof, authority, current ownership, checkpoint freshness,
STARTED, transport and receipt semantics remain there. The wrapper never
retries, rearms, bypasses authority or performs a speculative claim lookup.
With missing trusted dependencies, no-claim reconcile and new PREPARED/no-send
outcomes retain lower-layer semantics; claimed recovery requires neither a
current checkpoint nor write credentials and never resends.

Egress validates known state/code pairs, exact keys, nullable or required
action hash as applicable, and VERIFIED receipt hash and operation-specific
closed locator: creation issue_number/issue_id; material room/comment_id;
control, initial-open, aux and historical signal room/physical_ref; close
room/issue_id/event_id. Positive integers exclude booleans, and physical
reference room must match locator room. An ordinary exception or malformed
result after delegation is EFFECT_UNKNOWN/TRUSTED_RESULT_INVALID with null
action_key, not evidence of no send. Process termination remains a
lost-response recovery case. No arbitrary delegate exception/body/extra fields
are returned.

This is staged composition only. It does not establish isolation against
arbitrary Python code in the writer process, bounded CPU/heap behavior,
credential custody across processes, filesystem rollback resistance, removal of
the existing connector/direct-write bypass, or live deployment. Those require
separate 9b/9c contracts, implementation and evidence. Tests use synthetic
transport and existing real local-store/fence fixtures, not GitHub mutation.


### 9b-A — bounded one-shot IPC framing and trusted session binding

The staged local stream protocol uses a 10-byte request header: magic VPNG,
version 1, reconcile flag (exactly 0 or 1), unsigned big-endian 32-bit original
UTF-8 byte count. Nonzero length is bounded by MAX_INPUT_BYTES, followed by
exact bytes and EOF after client write-half-close. No nested JSON envelope,
worker role/session/owner metadata, or one-packet assumption. The receiver
reads incrementally in chunks no larger than 64 KiB, rejects ancillary data
and MSG_CTRUNC/MSG_TRUNC, and applies one absolute monotonic deadline across
header, body, EOF and UTF-8 decoding. No full-body eager allocation from the
header. Original JSON remains opaque; accepted 9a owns canonical semantic
admission.

Trusted caller creates a one-shot WriterInvocation from detached immutable
SessionBinding (role, incarnation, positive owner generation, bounded session
ID) and a trusted local handler. After complete validated frame and EOF it
attempts exactly one handler entry with the exact 9a request dict and this
trusted binding. Endpoint possession is delegation of the same session,
not fresh identity. No SO_PEERCRED/UID/PID identity assertion, worker
registration, role selection or owner-authority lookup in this framing unit.

Response: 9-byte VPNR/version-1/unsigned big-endian length header, bounded
canonical JSON (maximum 4096 bytes), EOF. Closed outcomes: INGRESS_REJECTED
with only state (trusted local rejection before handoff); RESULT with
state and the trusted handler's closed accepted 9a result union; or
HANDOFF_UNCERTAIN with only state. Reuse accepted 9a result validation,
including the two wrapper diagnostics, without taking operation identity
from worker JSON. The actual operation/result association remains the trusted
handler's responsibility. No exception text in wire results. Response send
has the same absolute deadline or a separately supplied absolute deadline.
The trusted response deadline must be finite/current before request reception
and rechecked immediately before handoff after the complete frame and EOF.
If no bounded response window exists before handler entry, reject locally
as INGRESS_REJECTED without calling the handler.
Set the local handoff boundary before handler entry; handler exception,
malformed result, deadline overrun or failed response write after that
boundary is uncertain, not no-attempt. Server's returned outcome is local
knowledge, not proof of client delivery. Client returns uncertainty on any
absent, malformed, truncated, late or reset response, including when server
locally rejected before handoff. No automatic retries. Reconciliation after
uncertainty requires the exact retained/spooled original; durable scheduler
recovery admission belongs to 9b-C and cannot be self-selected by the flag.

This module creates no worker processes/threads and performs no real
credential/GitHub I/O. It bounds logical frame size and receive chunks, not
decoded/canonicalization heap, aggregate concurrency or handler runtime.
A synchronous handler cannot be interrupted by this module; an overrun
observed on return is uncertain. Actual launch/session provenance,
process/UID/CPU/heap/deadline supervision, durable admission and recovery
spool, and alternate-path/live deployment proofs remain 9b-B, 9b-C and 9c.
Tests use synthetic local handler and Linux socketpairs only.


### 9b-B — staged trusted launcher and one-shot writer-child limits

This is a **staged Linux process-boundary proof**, not a live writer
deployment. The reviewed supervisor owns one active invocation slot per
instance and has no queue. Its trusted caller must establish a single
supervisor for a pinned store set; multiple independent supervisor
instances are not coordinated by this lock. The closed launch specification
pins session metadata, four distinct opaque store identities (owner,
runtime, attempt, input), positive finite hard limits and wall duration.
Store identities are diagnostic pins only in this unit: no store is opened,
created, reset, repaired or replaced, no actual capability or credential
is loaded, and no GitHub transport runs. Explicit trusted replacement of a
session changes its pin; restarting the same spec does not.

The only executable path is the trusted interpreter and fixed reviewed
child entrypoint from the trusted installation. The supervisor supplies
a fixed absolute cwd, isolated Python (-I -S -B), explicit environment,
DEVNULL stdio, close_fds and exact pass_fds; there is no shell, preexec_fn,
worker-configurable executable or unreviewed callable. Trusted installation,
supervisor, root and kernel integrity are prerequisites, not claims against
their compromise. A worker frame cannot choose the session, limits, paths
or probe. The child installs and verifies hard AS, CPU, NOFILE and NPROC
limits before reading bootstrap or parsing a request; the writer sets
NO_NEW_PRIVS and non-dumpable before reading dummy protected material.
In privileged probe mode, fixed setpriv clears groups and all capability
sets, sets distinct non-root UID/GID and NNP, then the child checks actual
identity, capabilities, descriptors and environment. The worker receives
only its client endpoint. The writer receives its server endpoint and
a separate private bootstrap/diagnostic socket. Same-identity mode is
explicitly a test mode and proves no UID separation. Only dummy material is
used in the privileged test, never an owner token or write credential.

Each transferred parent-side descriptor is closed immediately after the
respective spawn. Partial launch failure closes untransferred endpoints,
terminates and reaps every started immediate child, and reclaims the slot
only after confirmed reaping and closure of supervisor-owned endpoints.
The returned client endpoint in the direct test API is transferred to its
trusted caller, not retained. No additional listening endpoint exists.
An abrupt process exit must not be masked by a retained supervisor copy.
A duplicated client endpoint delegates the same pinned session, not a
new identity or admission. Cleanup has an invocation-scoped identity: the
watcher remains inert behind an activation gate until successful transfer
from the launcher. A failed or interrupted thread start leaves cleanup with
the launcher, even if the thread actually started. A successful transfer
leaves reaping and control closure with the watcher alone. Slot release
checks the exact active invocation identity after closure and reaping; a
stale watcher cannot release a later invocation. Diagnostic failure is not
reaping failure and does not suppress publication of the completion record.

One absolute monotonic deadline covers spawn, trusted bootstrap, IPC
request, handler, response and exit. The supervisor independently waits
until that deadline, then kills/reaps the reviewed immediate children
and closes its control socket before releasing capacity. A launch/setup
failure is conservatively surfaced as a launch error without action
result; the slot remains unavailable if reaping cannot be established.
This is conditional on a running trusted supervisor and functioning
kernel; it does not assert that an uninterruptible kernel operation or
supervisor death permits instantaneous physical reap at the deadline.
A child exit, missing response or deadline expiry after possible 9b-A
handoff never authorizes a retry or proves no-attempt. A separate bounded
diagnostic report records closed test observations and the synthetic
handler-entry marker; it is not an action result, and absence of that
marker proves nothing about handler entry.

The reviewed writer child has no fork/exec/subprocess path in this staged
implementation. NPROC is supplementary, not a general tree bound or
concurrency admission proof. No whole hostile worker-tree containment is
claimed: worker descendants, aggregate cgroup enforcement, trusted
credential provisioning, actual store reopen/admission, crash recovery and
alternate write-path exclusion remain separately reviewed work. There is
no production numeric memory/CPU limit derived from the wire maximum.
Directed tests generate real frozen auxiliary actions using the accepted
projection/compact/proof primitives, exercise the pure _bound proof path
inside the limited child and measure exact input bytes, RSS high-water
mark and CPU. This demonstrates those tested sizes and semantic binding,
not execution of a real effect, every valid input up to the wire bound, or
maximum admissible resource consumption.


### 9b-C-A — durable admission spool and bounded recovery state (staged)

The reviewed spool is a local, trusted, existing-only SQLite component. It
does not call TrustedWriter.invoke, acquire owner or attempt fences, open or
modify the paired stores, load credentials, perform GitHub I/O, schedule
recovery, grant authority, or authorize a retry. C-B must compose it under the
outer admission lock; 9c must establish deployment, credential custody,
bypass exclusion and actual resource/continuity premises.

There is one authoritative serialized budget per exact AttemptStore/InputStore
pair across all roles and launcher/recovery instances (or disjoint pairs with
disjoint budgets). First provisioning requires caller-established verified-empty
pair provenance and exclusion of bypass consumption. C-A does not itself
establish emptiness, occupancy or historical continuity. Provisioning creates a
new path exclusively, initializes the exact schema in a FULL-synchronous
rollback-DELETE transaction and fsyncs the directory. Runtime open is explicit,
existing-only, with the caller's trusted physical inode pin; no implicit
create, migrate, reset or repair. An open view holds an O_PATH inode pin and
checks file identity, ownership, 0600 mode and a local size bound before/after
operations. The storage pin includes the spool ID, distinct attempt and input
IDs, normalized logical repository, epoch, schema version, hard quotas, and
the exact canonical full configuration bytes (not only a digest). Repository
case and the signal room are preserved exactly in those bytes. The scope and
quotas are fixed for the shared pair; role, incarnation, actor and trusted
resource-policy identity are per-record. Current session/owner generation
comes from trusted bootstrap; first session/generation is retained only as
diagnostic provenance, not permanent identity or authority. A current role
view must pass the accepted model/bindings/config intersection and exact
session-role check. Recovery under a newly authorized same-role owner is
compatible with immutable first-session provenance.

Before READY, the trusted view validates the closed request type and UTF-8
byte bound, exact canonical frozen fields, full configuration pin, selected
role/incarnation/actor, original reconcile mode, and the supported operation
set. It runs the accepted pure _bound proof binding without instantiating an
effect-capable writer. This is not permission or substitute for the actual
independent ingress and fences at invocation. Malformed originals do not
reserve capacity or create recovery work. The request ID is a hash of the exact
logical pair/scope, role, incarnation, actor, immutable mode and original
digest. Repeated identity compares the exact stored bytes and immutable
operation/scope/policy; it neither overwrites nor charges twice. A different
original or original mode has a separate reservation. A changed resource
policy under the same identity is rejected. No credential, arbitrary
exception, raw remote response or worker-selected store, path, policy or quota
is accepted as metadata.

Every admission pessimistically reserves one record, exact original bytes,
a fixed bounded metadata slot (4096 logical bytes) and a full canonical
IPC RESULT envelope slot (4096 bytes). New-send original mode additionally
reserves two AttemptStore rows, one InputStore row and exactly the original
byte length in downstream retained-input capacity. Original reconcile-only
mode reserves zero new downstream rows/bytes. Forced recovery preserves the
immutable original mode and the existing charge. Quotas are pair-wide,
serialized by BEGIN IMMEDIATE; the admission and exact original commit
together. No automatic refunds, deletion, compaction, quota reclamation or
unbounded result history exist. Quotas are hard logical admission bounds,
not a guarantee of physical SQLite/journal free space, CPU/RSS ceilings,
power-loss durability or rollback resistance. C-B/9c own the relevant
external premises.

State transitions are short committed transactions with bounded monotone
versions and exact compare-and-set guards:

- READY records contain the admitted original and reservation, with no prior
  delegation. Marking the initial execution requires READY and the current
  version, revalidates the selected exact original/metadata and durably
  commits DELEGATION_MARKED before returning the exact original request.
- DELEGATION_MARKED is conservative uncertainty before any possible delegate
  entry, not proof of actual 9a invocation. Recovery re-marks either this
  state or a RESULT classified RECOVERY_REQUIRED, with a fresh guarded version,
  revalidates the exact immutable original and returns reconcile-only=true.
  The stored original mode/charge does not change.
- RESULT retains one bounded canonical full IPC RESULT envelope, including the
  operation-specific accepted 9a delegate union and the two exact wrapper
  diagnostics. A matching execution kind and marker version are required.
  A lost or uncommitted result leaves the durable marker. Invalid structure
  or source-impossible mode/key provenance leaves the marker and sticky
  uncertainty, with only a fixed diagnostic. An exhausted version fails
  closed. A later result does not append history.

The classification is distinct from mere result retention. INITIAL verified
is TERMINAL_VERIFIED; exact NO_ATTEMPT / NO_CLAIMED_EFFECT / null is
TERMINAL_NO_EFFECT only for an originally reconcile-only initial invocation.
INITIAL NO_ATTEMPT (other codes), BUSY, PREPARED and CONFLICT are retained
nonterminal; INITIAL UNRESOLVED or EFFECT_UNKNOWN is RECOVERY_REQUIRED.
FORCED_RECOVERY verified resolves uncertainty; exact null-key NO_CLAIMED_EFFECT
is NO_CLAIM_REARM_CANDIDATE; all other reachable closed non-verifying outcomes
remain RECOVERY_REQUIRED. A PREPARED or START uncertainty result on an actual
reconcile-only execution, initial new-send no-claim, a nonnull NO_ATTEMPT key,
or inconsistent EFFECT_UNKNOWN key provenance is source-impossible even
where the structural union permits it, and cannot replace the marker with
a misleading result. FENCED_INVOCATION_UNCONFIRMED and TRUSTED_RESULT_INVALID
have null keys; other EFFECT_UNKNOWN families have claimed/prepared keys.
Operation-specific receipt/locator validation reuses the accepted validator.
A no-claim observation does not establish future absence, continuity or
permission. In particular, an originally reconcile-only record never becomes
a send candidate. No RESULT-to-READY transition or re-arm API is implemented
in C-A. C-B must apply its independently accepted scheduling/authority rules
and outer serialization across the committed marker, actual invocation and
committed result; C-A CAS alone does not serialize external effects.

Pair-wide status/quota scans use count/sum/type/length and bounded metadata
only. Original, exact configuration and canonical RESULT envelope are BLOBs,
with storage class and byte lengths checked rather than TEXT character counts.
Only a selected record loads and revalidates its original and bounded result;
the inventory never returns retained payloads. Retained prior uncertainty
survives recovery wrapper rejection, BUSY, CONFLICT and source-impossible
PREPARED; only a verified result or the exact forced no-claim observation
resolves it. A failure to persist a result is not evidence of no delegation.
No unbounded result history is needed.

Directed offline evidence covers the accepted result family matrix,
source-tight provenance and operation-specific receipt bounds, exact config
and physical pin mismatches, original-mode charges, each quota edge,
idempotence/reopen, pair-wide metadata-only access to multiple large valid
UTF-8 originals, wrong BLOB storage classes, separate-process competing
admission/mark, and a real process exit during an uncommitted result update.
These are staged storage/binding tests, not a live credential, real effect,
exclusive outer admission lock, or full deployment proof.
