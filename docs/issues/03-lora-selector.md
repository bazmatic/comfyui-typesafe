# 03: Select one connected LoRA candidate or none

**What to build:** Let users wire visual Candidate nodes into a Selector that chooses exactly one known candidate or none, with inspectable probabilities and reasons. Reuse the shared judgment gateway and LoRA runtime; never blend candidates, generate filenames or silently substitute a fallback. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** 01 — Text Guard stops dependent work on a matching condition; 02 — Describe installed LoRAs through visual Candidate nodes.

**Status:** ready-for-agent

**Implementation:** complete (2026-09-26).

- [x] Register `TypeSafeLoraSelect` in category `TypeSafe` with connectable multiline nonblank text, native Autogrow candidate sockets capped at 1–100, confidence threshold default 0.5 in [0,1], advanced model default `jev-latest` and refresh ID default 0. Validate all inputs server-side.
- [x] Validate runtime candidate records, reject duplicate installed filenames and missing files before inference, and order sockets by numeric suffix. Map candidates to request-local IDs and reserve explicit `none` internally.
- [x] Extend the typed gateway and engine with one Choice evaluation. Send structured text and candidate selection context as evidence, excluding local absolute paths, strengths, tensors and credentials. Copy accepted settings only from known candidate records.
- [x] Validate answer/question types and IDs, exact option coverage, finite probabilities and confidence in [0,1], sum within 0.01 of 1, and a known winner with maximal probability within 1e-6 tolerance. Reject invalid responses without normalization or fallback.
- [x] Apply policy in order: exact maximum tie yields none with `ambiguous`; raw none yields `no_match`; confidence below threshold yields `low_confidence`; otherwise select with `selected`. Equality is accepted, and near-ties use the configured confidence policy.
- [x] Emit frozen `LoraSelection` on `TYPESAFE_LORA_SELECTION`, with Python None representing absence internally. Also output filename, has-match, raw confidence, verbatim trigger words and formatted details containing raw winner, probabilities and effective outcome. Filename/triggers are empty for none.
- [x] Offline tests cover clear winner, explicit none, low/equal confidence, exact ties including threshold zero, single/100/zero candidates, numeric ordering, duplicates, missing files, wrong types, missing/extra IDs, unknown winner, NaN/infinity, invalid sums and nonmaximal winners. Provider errors remain errors.
- [x] Verify successful output reuse and reruns after refresh, model and relevant input changes using normal ComfyUI caching, with no secondary inference cache.
- [x] Browser/host checks prove custom socket connectivity, Autogrow expansion and workflow save/load round-trip. Candidate aggregates pack correctly and remain distinct from mapped execution batch lists.


## Implementation evidence — 2026-09-26

Implemented and registered the native V3 Selector, frozen Choice/selection records,
strict shared HTTP Choice parsing, deterministic selection policy, metadata-only
candidate preflight, numeric socket ordering and diagnostic presentation outputs.
The existing transport lifecycle/retry/cancellation handling is shared by both
judgment kinds. No secondary inference cache or weight loading was added.

All 30 offline tests pass using ComfyUI's Python environment. New coverage includes
clear/none/low/equal-confidence outcomes, exact and near ties, single/100/zero
candidate cases, numeric ordering, duplicate/missing/invalid records, malformed
provider fields and distributions, finite bounds, exact option coverage, winner
tolerance and immutable collections. A loopback HTTP server checks the actual
Choice envelope and malformed-success rejection without paid inference.

The actual CPU prompt executor validates custom candidate and selection links,
packs growing sockets into one candidate dictionary, and preserves that aggregate
when mapping over a two-text batch. It reuses unchanged successful output and
reruns after refresh, model, threshold, text, candidate description, strength,
trigger and file changes. Removing a file stops execution before another judgment.
The installed host names growing sockets candidate0 through candidate99.

Browser smoke test completed in Chrome against an isolated CPU host on loopback,
with frontend 1.37.11 and no TypeSafe API key. Created Candidate and Selector nodes
through the node library, wired two Candidate outputs, and observed candidate1
then candidate2 appear as connections were added. Saved the workflow as
`typesafe-selector-smoke`, closed it, and reopened it from the Workflows sidebar.
Both candidate links and the spare growing socket remained visible after reload.
The saved JSON also contains the two namespaced candidate links and the unconnected
next socket. No judgment or weight loading was requested during this UI check;
selection execution and diagnostics are covered by the offline host tests above.
Live provider/model semantic quality remains unverified.
