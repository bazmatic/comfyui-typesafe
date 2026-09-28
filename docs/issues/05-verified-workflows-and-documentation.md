# 05: Deliver verified example workflows and setup documentation

**What to build:** Give users two verified visual workflows and enough setup, compatibility and operating guidance to use the four nodes confidently on the tested ComfyUI revision. Complete host/browser acceptance for the integrated package. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** 01 — Text Guard stops dependent work on a matching condition; 04 — Apply the selected LoRA with exact settings.

**Status:** ready-for-agent

**Implementation:** complete (2026-09-28).

- [x] Export and reopen a visual guard workflow wired ahead of an expensive dependent consumer, proving passing text continues and rejection prevents dependent execution.
- [x] Export and reopen a visual workflow with two Candidate nodes feeding Selector and Apply, proving accepted settings reach the loader and none preserves the base model/CLIP. Show trigger-word composition as an explicit user action rather than automatic prompt mutation.
- [x] Run offline tests and integrated host/browser smoke checks for all four registrations, widget/schema validation, custom sockets, Autogrow expansion/save-load, decision diagnostics, normal mapped execution and cache/refresh behaviour. Fix integration defects discovered by these checks.
- [x] Verify actual ComfyUI interrupt timing during async evaluation and document observations and deadline fallback. Explain that guard rejection does not undo prior work, stop all independent work, clear queued prompts or interrupt other users.
- [x] Record exact tested backend and frontend versions and the verification results. Do not claim historical-version support or treat fixture tests as live API/model-quality evidence.
- [x] Provide package metadata and development test dependencies, plus setup guidance for server-only credentials, deadline configuration, installed LoRAs, wiring, output meanings and actionable errors. Startup and metadata-only nodes must work without credentials.
- [x] Document text/description transmission to TypeSafe, package logging exclusions and ComfyUI's possible inclusion of node inputs in error details. Explain user responsibility for LoRA compatibility and preserve visibility of core warnings.
- [x] Document threshold uncertainty, pinned model IDs, saved decision details, refresh semantics, threshold-triggered re-inference and file metadata fingerprint limits. Describe opt-in live quality evaluation as separate from completion of offline/host acceptance.
- [x] Remove superseded scaffold-only public nodes/contracts from the final four-node package. Document standalone distribution because the host ignores custom nodes; do not create a new Git repository as part of this ticket.


## Implementation evidence — 2026-09-28

Added two [visual examples](../../examples/README.md), saved and reopened in
frontend 1.37.11. The exported graphs execute through the actual CPU prompt
executor with lightweight replacements for expensive model operations. Tests prove
Guard pass/reject behavior, exact selected strengths, none object identity,
explicit trigger composition and decision previews. All 38 offline tests pass.

[Verification results](../verification.md) record exact versions, browser evidence,
fixture boundaries and real host interrupt behavior. A pending HTTP request remains
active after the host interrupt flag is set; response completion or the configured
deadline bounds the wait, and dependent work does not run. Browser Guard diagnostics
used a temporary fake gateway; no paid calls or real-weight rendering occurred.

The README and example guide cover installation, server credentials, deadlines,
all four nodes, actionable errors, privacy, compatibility, cache limits and live
quality evaluation as a separate task. Package metadata declares aiohttp; tests use
standard-library unittest plus the installed host dependencies, with no additional
test dependency. This remains the existing standalone repository with exactly four
public TypeSafe registrations.
