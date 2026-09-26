# TypeSafe visual decision nodes

Implementation in progress: [ticket 01](docs/issues/01-text-guard.md) (Text Guard) is implemented. Only the V3
Text Guard is currently registered. The preliminary Judgment/Selector/Apply
scaffold is superseded; the visual LoRA nodes arrive in subsequent tickets.

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

## Offline validation

From the ComfyUI root, using its Python environment:

```sh
.venv/bin/python custom_nodes/comfyui-typesafe/tests/run.py
```

Tests use a fake gateway and a loopback HTTP server with fake credentials. They
make no paid API calls. The suite exercises the actual CPU-mode prompt executor,
including dependent-node rejection and normal cache invalidation. Loopback socket
access is required for transport tests.

For a checkout outside the host's custom-node directory, use the host's Python
environment and give the runner its ComfyUI path:

```sh
/path/to/ComfyUI/.venv/bin/python tests/run.py --comfyui-root /path/to/ComfyUI
```

ComfyUI and its dependencies must already be installed; the custom-node package
does not bundle them. The tests themselves use Python's standard unittest library.

Validated on Python 3.10.13 with backend revision
`3c1a1a2df82fc6c7aa20a3c8301d1c632e1a1d87`. Installed frontend package: 1.37.11;
browser behaviour and real host interrupt timing are not yet smoke-tested.
The provider contract was checked against the
[HTTP reference](https://docs.typesafe.ai/api) and
[Noul documentation](https://docs.typesafe.ai/primitives/noul) on 2026-09-26.

This is an independent Git repository inside the host's ignored custom-node
directory. Commit and push package changes from this directory. ComfyUI's Git
history remains separate.
