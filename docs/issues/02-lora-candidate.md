# 02: Describe installed LoRAs through visual Candidate nodes

**What to build:** Let users describe an installed LoRA and its application settings entirely through widgets, producing immutable metadata on a namespaced socket. Candidate creation works without TypeSafe credentials, inference or weight loading. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Register `TypeSafeLoraCandidate` as a native V3 node in category `TypeSafe`, exposing installed-name combo, required nonblank description, model/CLIP strengths defaulting to 1.0, and trigger words defaulting to empty.
- [ ] Emit a frozen `LoraCandidate` record on `TYPESAFE_LORA_CANDIDATE`, retaining installed name, description, both strengths and verbatim trigger words. Runtime records remain out of workflow JSON.
- [ ] Validate exact membership in the installed LoRA list at execution, accepting ComfyUI relative names including subdirectories. Reject arbitrary absolute paths, missing files and placeholder entries; show a clear setup error when no LoRAs exist.
- [ ] Validate finite strengths within −100 to 100 server-side and in widgets. Reject blank descriptions; never generate trigger words or claim model compatibility from metadata.
- [ ] Establish the LoRA runtime boundary for listing, file validation and fingerprinting with production and fake adapters. Candidate execution performs no weight loading or provider request.
- [ ] Fingerprint resolved file identity, size and nanosecond mtime so ordinary replacement/removal invalidates cached outputs. Document through tests that no cryptographic content identity is promised.
- [ ] Offline tests and host schema checks cover subdirectory names, empty libraries, stale names, invalid descriptions/strengths, immutable records, credential-free execution and cache invalidation after file replacement/removal.
