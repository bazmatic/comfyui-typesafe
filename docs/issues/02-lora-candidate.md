# 02: Describe installed LoRAs through visual Candidate nodes

**What to build:** Let users describe an installed LoRA and its application settings entirely through widgets, producing immutable metadata on a namespaced socket. Candidate creation works without TypeSafe credentials, inference or weight loading. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Implementation:** complete (2026-09-26).

- [x] Register `TypeSafeLoraCandidate` as a native V3 node in category `TypeSafe`, exposing installed-name combo, required nonblank description, model/CLIP strengths defaulting to 1.0, and trigger words defaulting to empty.
- [x] Emit a frozen `LoraCandidate` record on `TYPESAFE_LORA_CANDIDATE`, retaining installed name, description, both strengths and verbatim trigger words. Runtime records remain out of workflow JSON.
- [x] Validate exact membership in the installed LoRA list at execution, accepting ComfyUI relative names including subdirectories. Reject arbitrary absolute paths, missing files and placeholder entries; show a clear setup error when no LoRAs exist.
- [x] Validate finite strengths within −100 to 100 server-side and in widgets. Reject blank descriptions; never generate trigger words or claim model compatibility from metadata.
- [x] Establish the LoRA runtime boundary for listing, file validation and fingerprinting with production and fake adapters. Candidate execution performs no weight loading or provider request.
- [x] Fingerprint resolved file identity, size and nanosecond mtime so ordinary replacement/removal invalidates cached outputs. Document through tests that no cryptographic content identity is promised.
- [x] Offline tests and host schema checks cover subdirectory names, empty libraries, stale names, invalid descriptions/strengths, immutable records, credential-free execution and cache invalidation after file replacement/removal.


## Verification evidence

The offline suite passes all 21 tests using the installed ComfyUI Python
runtime. New Candidate tests exercise the native V3 schema and typed socket,
credential-free metadata-only execution, frozen records, exact installed relative
names, server and widget numeric bounds, empty libraries and stale files.

The actual CPU prompt executor reuses identical Candidate output, reruns after
metadata widget edits and file replacement, and stops downstream execution after
file removal. Production-adapter tests verify resolved path, device/inode, size
and nanosecond mtime identity and sanitized errors after directory removal. An
explicit same-size in-place rewrite with restored mtime leaves the fingerprint
unchanged, demonstrating the documented absence of content hashing.

Browser interaction remains part of the workflow-verification ticket. Selector
and Apply are intentionally not implemented by this ticket. No live API calls,
model weights or credentials were needed for Candidate validation.
