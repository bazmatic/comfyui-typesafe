# TypeSafe visual decision nodes

Implementation in progress: [Text Guard](docs/issues/01-text-guard.md),
[LoRA Candidate](docs/issues/02-lora-candidate.md),
[LoRA Selector](docs/issues/03-lora-selector.md), and
[Apply Selected LoRA](docs/issues/04-apply-selected-lora.md) are implemented and registered
as native V3 nodes. Verified example workflows remain for the next ticket.

See the [technical design](docs/design.md) and [implementation tickets](docs/issues/).
These documents and tickets were brought across from the host workspace when this
repository was created. Continue package planning here.

## Text Guard setup

Clone this repository into ComfyUI's custom-node directory, then restart ComfyUI:

```sh
git clone https://github.com/bazmatic/comfyui-typesafe.git /path/to/ComfyUI/custom_nodes/comfyui-typesafe
```

This repository is private, so cloning requires GitHub access. Set
`TYPESAFE_API_KEY` in the server environment before requesting a judgment. No key
is needed to import/register the extension. Optionally set
`TYPESAFE_TIMEOUT_SECONDS` to a number from 1–120 (default 30).

Add **TypeSafe · Text Guard**. Enter or connect text, edit the condition if needed,
and connect its text output before work that should depend on a successful guard.
At or above `stop_threshold`, the node raises an execution error and supplies no
normal outputs. Below it, the original text passes through alongside probability
and JSON decision details. A rejection does not undo completed work, clear queued
prompts or globally interrupt other work.

Unchanged successful runs use ComfyUI's cache. Change `refresh_id` to request a
fresh judgment; it is not a model seed. Changing model or threshold also reruns
inference. Use a pinned provider model ID and save decision details when
reproducibility matters; `jev-latest` can change remotely.

Text is sent to TypeSafe during inference. The package does not log source text,
keys, provider bodies or headers. ComfyUI itself can include node inputs in error
details, so this is not end-to-end redaction. Thresholds are starting settings,
not accuracy guarantees. Live model quality has not been evaluated.

## LoRA Candidate setup

Install a LoRA in a configured ComfyUI LoRA folder, refresh the node list, and add
**TypeSafe · LoRA Candidate**. Choose its exact installed name (subdirectories are
supported), describe when it is appropriate, and set model/CLIP strengths between
−100 and 100. Both strengths default to 1.0. Optional trigger words are copied
verbatim; they are never generated or inserted into prompts.

The node emits immutable metadata on `TYPESAFE_LORA_CANDIDATE`. It performs no
inference or weight loading and needs no API key. Empty libraries and stale names
produce setup errors. Candidate records stay in runtime memory; workflow JSON
contains the ordinary widget inputs and connections. The Selector
consumes this socket; Apply Selected LoRA applies its selection. Users remain
responsible for choosing LoRAs compatible with their base model.

ComfyUI caches unchanged candidates. Changes to widget inputs or to the resolved
file path, device/inode, size or nanosecond modification time invalidate that cache.
Removal prevents downstream use of a stale candidate. This checks file metadata,
not content hashes: an in-place edit preserving size and timestamp can remain
cached, so change a widget or restart in that case. Linked filenames are checked
on every execution because the host cannot inspect their values while creating
cache keys.

## LoRA Selector setup

Add **TypeSafe · LoRA Selector**, enter or connect the selection text, and connect
1–100 Candidate outputs to its growing candidate inputs. Each candidate must name
a different installed file. The node verifies records and installed files before
making one TypeSafe Choice request over the candidates plus an explicit none option.
Input socket suffixes determine numeric ordering; filenames never come from generated text.

The authoritative `selection` output is immutable and keeps the accepted candidate's
exact settings together for the Apply node. Presentation outputs expose
`lora_name`, `has_match`, raw `confidence`, verbatim `trigger_words`, and JSON
`decision_details` with the raw winner, option probabilities, filename mapping,
threshold and effective outcome. A none selection emits empty filename and triggers.
It does not select a fallback, combine LoRAs, or insert trigger words into your text.

Exact maximum ties yield `ambiguous`, including with threshold zero. Otherwise a
raw none yields `no_match`, confidence below `min_confidence` yields `low_confidence`,
and equality or higher yields `selected`. Near-ties follow the confidence threshold.
API failures and malformed responses remain errors, never successful none outcomes.
The default confidence threshold is 0.5; it has not been calibrated on your data.

Selection text, installed relative filenames and descriptions are sent to TypeSafe.
Local resolved paths, strength settings and trigger words are excluded from the
selection state. Keep credentials in the server environment. Successful output uses
ComfyUI's cache with no additional inference cache: changing refresh ID, model,
threshold, text or candidate inputs reruns selection. Normal Candidate file
fingerprints propagate replacement/removal through that cache.

## Apply Selected LoRA setup

Connect the Selector's `selection` output and your base MODEL and CLIP to
**TypeSafe · Apply Selected LoRA**. Connect its MODEL and CLIP outputs to downstream
conditioning/sampling. None returns the exact original objects without filesystem
access or loader calls. An accepted selection rechecks the installed file and
calls ComfyUI's core LoRA loader once with the exact stored strengths. Zero/zero
strengths remain a valid selection: the file is validated, then core returns the
original objects without reading weights. Application needs no API credentials.

Missing files and loading failures are visible errors; no runner-up is substituted.
Core compatibility warnings and useful error details remain visible, and host
interrupts retain their normal behaviour. Trigger words are never inserted into text.

A directly available selection fingerprints resolved identity, size and nanosecond
mtime using a tuple. In ordinary linked workflows, this host supplies `None` instead
of linked values during its cache-key pass. Apply therefore conservatively reruns
on every prompt, including downstream work, while unchanged upstream Selector
judgments remain cached. This also protects cached selections from other custom
nodes without Candidate ancestry. Each application creates a fresh core loader,
so filename-only weight caching cannot reuse stale weights after replacement.
The none path performs no file access even during this fingerprint pass.

## Offline validation

From the ComfyUI root, using its Python environment:

```sh
.venv/bin/python custom_nodes/comfyui-typesafe/tests/run.py
```

Tests use a fake gateway and a loopback HTTP server with fake credentials. They
make no paid API calls. The suite exercises the actual CPU-mode prompt executor,
including dependent-node rejection, namespaced candidate/selection socket wiring,
Autogrow packing, mapped text batches, widget validation, selection cache reuse,
and cache invalidation on LoRA replacement/removal. The 36-test suite also checks
Choice distributions, exact ties, threshold equality, none outcomes and 100 candidates. Temporary LoRA files
contain deliberately invalid weight data to verify metadata-only execution. Application
tests exercise the real core loader with mocked weight decoding/patching, exact
settings, zero strengths, warnings, errors and interrupts; real weight compatibility
and rendered output have not been tested. Actual host execution also verifies
linked-selection reruns, upstream inference reuse, stale-file rejection and none
object identity without runtime access. Loopback socket
access is required for transport tests.

For a checkout outside the host's custom-node directory, use the host's Python
environment and give the runner its ComfyUI path:

```sh
/path/to/ComfyUI/.venv/bin/python tests/run.py --comfyui-root /path/to/ComfyUI
```

ComfyUI and its dependencies must already be installed; the custom-node package
does not bundle them. The tests themselves use Python's standard unittest library.

Validated on Python 3.10.13 with backend revision
`3c1a1a2df82fc6c7aa20a3c8301d1c632e1a1d87`. Frontend package 1.37.11 was smoke-tested in Chrome for custom Candidate/Selector
connections, growing sockets and workflow save/close/reopen. This UI check made no
provider calls. Real host interrupt timing remains to be verified.
The provider contract was checked against the
[HTTP reference](https://docs.typesafe.ai/api) and
[Noul documentation](https://docs.typesafe.ai/primitives/noul),
[Choice documentation](https://docs.typesafe.ai/primitives/choice) and
[function-calling cookbook](https://docs.typesafe.ai/cookbooks/function_calling) on 2026-09-26.

This is an independent Git repository inside the host's ignored custom-node
directory. Commit and push package changes from this directory. ComfyUI's Git
history remains separate.
