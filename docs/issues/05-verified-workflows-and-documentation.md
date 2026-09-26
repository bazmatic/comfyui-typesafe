# 05: Deliver verified example workflows and setup documentation

**What to build:** Give users two verified visual workflows and enough setup, compatibility and operating guidance to use the four nodes confidently on the tested ComfyUI revision. Complete host/browser acceptance for the integrated package. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** 01 — Text Guard stops dependent work on a matching condition; 04 — Apply the selected LoRA with exact settings.

**Status:** ready-for-agent

- [ ] Export and reopen a visual guard workflow wired ahead of an expensive dependent consumer, proving passing text continues and rejection prevents dependent execution.
- [ ] Export and reopen a visual workflow with two Candidate nodes feeding Selector and Apply, proving accepted settings reach the loader and none preserves the base model/CLIP. Show trigger-word composition as an explicit user action rather than automatic prompt mutation.
- [ ] Run offline tests and integrated host/browser smoke checks for all four registrations, widget/schema validation, custom sockets, Autogrow expansion/save-load, decision diagnostics, normal mapped execution and cache/refresh behaviour. Fix integration defects discovered by these checks.
- [ ] Verify actual ComfyUI interrupt timing during async evaluation and document observations and deadline fallback. Explain that guard rejection does not undo prior work, stop all independent work, clear queued prompts or interrupt other users.
- [ ] Record exact tested backend and frontend versions and the verification results. Do not claim historical-version support or treat fixture tests as live API/model-quality evidence.
- [ ] Provide package metadata and development test dependencies, plus setup guidance for server-only credentials, deadline configuration, installed LoRAs, wiring, output meanings and actionable errors. Startup and metadata-only nodes must work without credentials.
- [ ] Document text/description transmission to TypeSafe, package logging exclusions and ComfyUI's possible inclusion of node inputs in error details. Explain user responsibility for LoRA compatibility and preserve visibility of core warnings.
- [ ] Document threshold uncertainty, pinned model IDs, saved decision details, refresh semantics, threshold-triggered re-inference and file metadata fingerprint limits. Describe opt-in live quality evaluation as separate from completion of offline/host acceptance.
- [ ] Remove superseded scaffold-only public nodes/contracts from the final four-node package. Document standalone distribution because the host ignores custom nodes; do not create a new Git repository as part of this ticket.
