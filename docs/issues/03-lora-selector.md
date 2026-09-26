# 03: Select one connected LoRA candidate or none

**What to build:** Let users wire visual Candidate nodes into a Selector that chooses exactly one known candidate or none, with inspectable probabilities and reasons. Reuse the shared judgment gateway and LoRA runtime; never blend candidates, generate filenames or silently substitute a fallback. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** 01 — Text Guard stops dependent work on a matching condition; 02 — Describe installed LoRAs through visual Candidate nodes.

**Status:** ready-for-agent

- [ ] Register `TypeSafeLoraSelect` in category `TypeSafe` with connectable multiline nonblank text, native Autogrow candidate sockets capped at 1–100, confidence threshold default 0.5 in [0,1], advanced model default `jev-latest` and refresh ID default 0. Validate all inputs server-side.
- [ ] Validate runtime candidate records, reject duplicate installed filenames and missing files before inference, and order sockets by numeric suffix. Map candidates to request-local IDs and reserve explicit `none` internally.
- [ ] Extend the typed gateway and engine with one Choice evaluation. Send structured text and candidate selection context as evidence, excluding local absolute paths, strengths, tensors and credentials. Copy accepted settings only from known candidate records.
- [ ] Validate answer/question types and IDs, exact option coverage, finite probabilities and confidence in [0,1], sum within 0.01 of 1, and a known winner with maximal probability within 1e-6 tolerance. Reject invalid responses without normalization or fallback.
- [ ] Apply policy in order: exact maximum tie yields none with `ambiguous`; raw none yields `no_match`; confidence below threshold yields `low_confidence`; otherwise select with `selected`. Equality is accepted, and near-ties use the configured confidence policy.
- [ ] Emit frozen `LoraSelection` on `TYPESAFE_LORA_SELECTION`, with Python None representing absence internally. Also output filename, has-match, raw confidence, verbatim trigger words and formatted details containing raw winner, probabilities and effective outcome. Filename/triggers are empty for none.
- [ ] Offline tests cover clear winner, explicit none, low/equal confidence, exact ties including threshold zero, single/100/zero candidates, numeric ordering, duplicates, missing files, wrong types, missing/extra IDs, unknown winner, NaN/infinity, invalid sums and nonmaximal winners. Provider errors remain errors.
- [ ] Verify successful output reuse and reruns after refresh, model and relevant input changes using normal ComfyUI caching, with no secondary inference cache.
- [ ] Browser/host checks prove custom socket connectivity, Autogrow expansion and workflow save/load round-trip. Candidate aggregates pack correctly and remain distinct from mapped execution batch lists.
