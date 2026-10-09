# Node reference and troubleshooting

Detailed behavior, caching rules, errors and test instructions for the four
TypeSafe nodes. For installation and example workflows, start with the
[README](../README.md).

## Installation and Text Guard setup

Clone this repository into ComfyUI's custom-node directory, then restart ComfyUI:

```sh
git clone https://github.com/bazmatic/comfyui-typesafe.git /path/to/ComfyUI/custom_nodes/comfyui-typesafe
```

Install the dependency listed in `pyproject.toml` with the same Python environment
that runs ComfyUI (`python -m pip install aiohttp`); no TypeSafe SDK is required.

This repository is private, so cloning requires GitHub access. Set
`TYPESAFE_API_KEY` in the server environment before requesting a judgment. No key
is needed to import/register the extension. Optionally set
`TYPESAFE_TIMEOUT_SECONDS` to a number from 1–120 (default 30).

Add **TypeSafe · Text Guard**. Enter or connect text, edit the condition if needed,
and connect its text output before work that should depend on a successful guard.
At or above `stop_threshold`, the node raises an execution error and supplies no
normal outputs. Below it, the original text passes through alongside probability
and JSON decision details. A rejection does not undo completed work, clear queued
prompts or globally interrupt other work. Independent branches may already have
executed; rejection does not interrupt other users.

On the tested host, pressing Interrupt does not cancel a pending TypeSafe HTTP
request. Downstream work stops when the request returns, or the configured request
deadline ends the wait with an error. The default deadline is 30 seconds. See the
[measured interrupt results](verification.md).

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
1–100 Candidate outputs to its growing candidate inputs. Several candidates may name
the same installed file with different descriptions, strengths or trigger words. The node verifies records and installed files before
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

## Troubleshooting

| Failure | Action |
| --- | --- |
| `ConfigurationError` | Set the server's `TYPESAFE_API_KEY`, check the 1–120 second timeout, and correct invalid inputs or missing installed LoRA names. Restart the server after changing its environment. |
| `ProviderUnavailable` | Check server network access and credentials, provider availability and the configured deadline, then rerun. This is an error, not a none selection. |
| `ProviderProtocolError` | The response did not match the supported provider contract. Check the requested model and provider API compatibility; do not treat this as a valid judgment. |
| `GuardRejected` | Inspect the condition, reported probability and threshold. Correct the upstream result or deliberately revise the condition before retrying. |
| `LoraApplicationError` | Re-select an installed file and confirm checkpoint/LoRA compatibility. Read the underlying core loader message; compatibility warnings remain visible. |

Startup and Candidate metadata evaluation require no credentials. Guard and
Selector require credentials when they actually request a judgment. No API key
belongs in workflow JSON. Only the four TypeSafe nodes above are public; the
examples also use ComfyUI's built-in nodes.

## Offline validation

From the ComfyUI root, using its Python environment:

```sh
.venv/bin/python custom_nodes/comfyui-typesafe/tests/run.py
```

Tests use a fake gateway and a loopback HTTP server with fake credentials. They
make no paid API calls. The suite exercises the actual CPU-mode prompt executor,
including dependent-node rejection, namespaced candidate/selection socket wiring,
Autogrow packing, mapped text batches, widget validation, selection cache reuse,
and cache invalidation on LoRA replacement/removal. The 38-test suite also checks
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

See [verification results](verification.md) for exact host/frontend versions,
exported graph execution, browser save/reopen checks and measured interrupt timing.
These are offline integration checks; opt-in live quality evaluation is ticket 06.
The provider contract was checked against the
[HTTP reference](https://docs.typesafe.ai/api) and
[Noul documentation](https://docs.typesafe.ai/primitives/noul),
[Choice documentation](https://docs.typesafe.ai/primitives/choice) and
[function-calling cookbook](https://docs.typesafe.ai/cookbooks/function_calling) on 2026-09-26.

This is an independent Git repository inside the host's ignored custom-node
directory. Commit and push package changes from this directory. ComfyUI's Git
history remains separate.
