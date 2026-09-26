# 04: Apply the selected LoRA with exact settings

**What to build:** Apply the Selector's authoritative selection to a model and CLIP through the existing core LoRA loader, preserving the original objects for none and failing visibly if an accepted file is stale. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** 03 — Select one connected LoRA candidate or none.

**Status:** ready-for-agent

**Implementation:** complete (2026-09-26).

- [x] Register `TypeSafeLoraApply` in category `TypeSafe` with required MODEL, CLIP and `TYPESAFE_LORA_SELECTION` inputs and MODEL/CLIP outputs. Validate runtime selection records rather than trusting socket names alone.
- [x] For none, return the exact input objects without file access, loader invocation or patching, including during fingerprint calculation.
- [x] For an accepted candidate, re-resolve and validate its installed name and delegate once to the core loader with the exact candidate strengths. Never call TypeSafe, reinterpret confidence, choose a runner-up or mutate prompt/trigger text.
- [x] Extend the LoRA runtime and fake with application operations. Surface stale files and loading errors as actionable `LoraApplicationError` failures while retaining useful core compatibility warnings/errors.
- [x] Preserve core zero-strength behaviour as a valid selection. Required CLIP remains consistent with the standard loader; model-only application is outside this ticket.
- [x] Fingerprint the selected file using resolved identity, size and nanosecond mtime. Avoid stale core weight caching by creating a loader per execution or invalidating retained loader state whenever the fingerprint changes.
- [x] Fake-runtime tests prove identical-object none behaviour, no none-path file reads, one selected load with exact settings, malformed-record rejection and stale-file errors. Host/cache tests prove ordinary file replacement/removal invalidates candidate/application outputs and cannot reuse stale weights.


## Implementation evidence — 2026-09-26

Registered native V3 Apply with required MODEL, CLIP and selection inputs. Runtime
records are revalidated; none bypasses the runtime entirely and preserves object
identity. Accepted records delegate through the runtime to one fresh core loader
with exact strengths. Selected-file availability is rechecked even for zero/zero
strengths. Loading failures retain the useful core error as an actionable
LoraApplicationError; core warnings and host interruption semantics are preserved.

All 36 offline tests pass in the installed host's Python environment. Six new
application tests cover schema, malformed/forged records, fake-runtime exact
settings, none without any runtime, direct tuple fingerprints, stale files, real
core loader fresh weight reads, zero strengths, visible warnings/errors and host
interrupt propagation. Weight decoding and patching are mocked: no real weights,
GPU work or paid inference are required.

The actual CPU prompt executor proves Apply reloads while an unchanged upstream
Selector judgment remains cached. Replacement invalidates the Candidate/Selector
path, and cached selection sources without Candidate ancestry still load fresh
weights after replacement and fail after removal. None preserves both original
objects across prompts with the application runtime removed entirely.

Host limitation: linked selection values arrive as None during fingerprinting.
Apply returns NaN in this case without file I/O, conservatively rerunning itself
and downstream consumers on every prompt. Directly available selected records
use resolved path/device/inode/size/nanosecond-mtime tuple fingerprints; directly
available none uses a stable tuple without I/O. A fresh core loader per execution
prevents its filename-only weight cache from returning stale data. The design's
ideal selective Apply caching cannot be achieved for arbitrary linked selection
sources with this host fingerprint API; this tradeoff is documented in the README.

Real model/LoRA compatibility and rendered output remain unverified; full visual
example workflows are ticket 05, and live semantic evaluation is ticket 06.
