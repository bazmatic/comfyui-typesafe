# 01: Text Guard stops dependent work on a matching condition

**What to build:** Replace the unvalidated guard scaffold with a native V3 Text Guard that evaluates a user-configured condition through TypeSafe. Passing judgments preserve the original text; matching judgments visibly stop dependent work in the current prompt. Establish the shared judgment boundary and production transport through this working slice. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Implementation:** complete (2026-09-26)

- [x] Register `TypeSafeTextGuard` using `ComfyExtension` and `io.ComfyNode`, in category `TypeSafe`. Provide connectable multiline text and condition inputs, threshold default 0.5 in [0,1], advanced model default `jev-latest`, and refresh ID default 0. Reject blank text, blank conditions, invalid models and invalid numeric values server-side.
- [x] Use the specified default service-failure condition, distinguishing actual failures from successful content discussing failures. Return original text byte-for-byte, probability and formatted decision details when probability is below the threshold. Equality and above raise dedicated `GuardRejected` containing probability and threshold, without input text or normal outputs.
- [x] Introduce frozen domain records with immutable collections, the closed typed Question/Judgment boundary, a `JudgmentGateway` protocol and fake, and an injected `DecisionEngine`. Keep question construction and pure decision policy outside node adapters and independent of ComfyUI.
- [x] Implement async Noul evaluation against the fixed TypeSafe HTTPS endpoint using aiohttp, one stable question ID, structured evidence, and server-side credentials read per request. Retain requested/returned model and token usage. Missing credentials do not prevent extension startup.
- [x] Validate response types, question IDs and finite probabilities in [0,1]. Expose configuration, unavailability and protocol errors through the specified sanitized error taxonomy; never turn a failure into a passing judgment or log text, credentials, raw bodies or headers.
- [x] Enforce a 30-second overall deadline, environment-configurable from 1–120 seconds, and connect timeout at most 10 seconds bounded by remaining time. Use at most two attempts, only retrying explicit 429/529 responses, respecting valid Retry-After within the deadline or short jittered backoff otherwise.
- [x] Disable redirects, retain TLS verification, cap bodies at 1 MiB, close per-evaluation sessions/responses, and propagate cancellation. Do not retry authentication, validation, ambiguous connection, timeout or malformed-success errors.
- [x] Offline fake-gateway and local HTTP server tests cover threshold boundaries, text preservation, valid and malformed Noul responses, missing key, 401/422, retry bounds/deadline, redirects, oversized bodies, invalid JSON, timeout and cancellation cleanup without paid inference.
- [x] Host integration proves registration/schema validity, async execution, rejection preventing a dependent sentinel from executing, successful output reuse, and re-evaluation after refresh/model/threshold changes. The stop is scoped to current-prompt scheduling, with no global interrupt or queue clearing.


## Comments

2026-09-26 — Implemented native V3 Text Guard, immutable Noul records, injected
DecisionEngine/gateway, sanitized async aiohttp transport and offline test suite.
Choice extends the closed Question/Judgment aliases in ticket 03. Only the new
Text Guard is registered during this intermediate slice; preliminary scaffold
Selector/Apply nodes are superseded pending their replacement tickets.

Validation: all 14 unittest tests passed, including a real loopback HTTP server
and the installed ComfyUI CPU-mode prompt executor. Verified original text,
threshold boundaries, malformed responses, bounded retries, deadline rejection,
timeout/cancellation session cleanup, successful output reuse and reruns after
refresh/model/threshold changes. Host rejection prevents a dependent sentinel.
The host test also validates the prompt against the native schema.

Backend: 3c1a1a2df82fc6c7aa20a3c8301d1c632e1a1d87; Python 3.10.13.
Frontend 1.37.11 is installed but browser validation and actual host interrupt
timing remain ticket 05. No live provider call or quality claim was made.
Package implementation is locally present in the host-ignored custom-node
directory; standalone versioning remains release preparation.

2026-09-26 — Standalone repository created in the existing custom-node directory.
This ticket and the remaining plan now travel with the package. The portable test
runner passes all 14 tests from the repository root; implementation files are now
tracked by this repository independently of ComfyUI.
