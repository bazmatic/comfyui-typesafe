# 04: Apply the selected LoRA with exact settings

**What to build:** Apply the Selector's authoritative selection to a model and CLIP through the existing core LoRA loader, preserving the original objects for none and failing visibly if an accepted file is stale. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** 03 — Select one connected LoRA candidate or none.

**Status:** ready-for-agent

- [ ] Register `TypeSafeLoraApply` in category `TypeSafe` with required MODEL, CLIP and `TYPESAFE_LORA_SELECTION` inputs and MODEL/CLIP outputs. Validate runtime selection records rather than trusting socket names alone.
- [ ] For none, return the exact input objects without file access, loader invocation or patching, including during fingerprint calculation.
- [ ] For an accepted candidate, re-resolve and validate its installed name and delegate once to the core loader with the exact candidate strengths. Never call TypeSafe, reinterpret confidence, choose a runner-up or mutate prompt/trigger text.
- [ ] Extend the LoRA runtime and fake with application operations. Surface stale files and loading errors as actionable `LoraApplicationError` failures while retaining useful core compatibility warnings/errors.
- [ ] Preserve core zero-strength behaviour as a valid selection. Required CLIP remains consistent with the standard loader; model-only application is outside this ticket.
- [ ] Fingerprint the selected file using resolved identity, size and nanosecond mtime. Avoid stale core weight caching by creating a loader per execution or invalidating retained loader state whenever the fingerprint changes.
- [ ] Fake-runtime tests prove identical-object none behaviour, no none-path file reads, one selected load with exact settings, malformed-record rejection and stale-file errors. Host/cache tests prove ordinary file replacement/removal invalidates candidate/application outputs and cannot reuse stale weights.
