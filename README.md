# TypeSafe nodes for ComfyUI

Use TypeSafe AI judgments to **stop a workflow when text reports a failure** or
**choose an installed LoRA from a prompt**.

The extension adds four nodes under the **TypeSafe** category:

| Node | What it does |
| --- | --- |
| **Text Guard** | Checks text against your condition. Passes it through or stops dependent work. |
| **LoRA Candidate** | Describes an installed LoRA, its strengths and optional trigger words. |
| **LoRA Selector** | Chooses one connected candidate—or none—based on your text. |
| **Apply Selected LoRA** | Applies the selected settings to MODEL and CLIP. None leaves both unchanged. |

## Install

You need an existing ComfyUI installation, access to this private repository, and
a TypeSafe API key to run Guard or Selector.

1. Clone into ComfyUI's `custom_nodes` directory:

   ```sh
   git clone https://github.com/bazmatic/comfyui-typesafe.git /path/to/ComfyUI/custom_nodes/comfyui-typesafe
   ```

2. Install the dependency using **the Python environment that runs ComfyUI**:

   ```sh
   python -m pip install aiohttp
   ```

3. Set the key in the environment used to launch the ComfyUI server, then restart it:

   ```sh
   export TYPESAFE_API_KEY="your-api-key"
   ```

Keep the key on the server; never put it in a node or workflow file. No TypeSafe
SDK is required. The extension loads without a key, and Candidate and Apply do
not call the API.

## Try a workflow

Open an example JSON in ComfyUI, or drag it onto the canvas. Replace the placeholder
checkpoint and LoRA filenames with compatible models you have installed.

| Example | Flow |
| --- | --- |
| [Guard before sampling](examples/guard-before-sampling.json) | Text Guard → positive text encoding → sampling |
| [Select and apply a LoRA](examples/select-and-apply-lora.json) | Two Candidates → Selector → Apply → encoding and sampling |

The [example guide](examples/README.md) explains the wiring, decision previews and
explicit trigger-word composition. Trigger words are never added automatically.

## Key behavior

- **Guard stops dependent work.** It rejects when probability meets or exceeds
  `stop_threshold`. It cannot undo completed work or stop independent branches.
- **Selector can abstain.** A none result, low confidence or an exact tie applies
  no LoRA. API failures remain errors.
- **Judgments are cached.** Change `refresh_id` to request a fresh one. Changing
  text, model or threshold also reruns inference. On the tested host, Apply and
  its downstream work rerun even when the selection judgment is cached.
- **Requests have a deadline.** `TYPESAFE_TIMEOUT_SECONDS` accepts 1–120 seconds
  (default 30). Interrupt may wait for the pending request to finish or time out.

## Privacy and validation

Guard sends text and its condition to TypeSafe. Selector sends selection text,
relative LoRA filenames and descriptions. Credentials stay in the server environment.
The package does not log source text, keys or provider bodies/headers, but ComfyUI
may include node inputs in error details.

Verified with ComfyUI **0.11.1**, frontend **1.37.11**, and **38 passing offline
tests**. Browser save/reopen checks also passed. Live judgment quality and real-weight
rendering remain unverified. Choose compatible LoRAs and tune thresholds for your
own cases; the defaults are starting points.

## Reference and development

- [Node reference and troubleshooting](docs/node-reference.md) — outputs, selection rules, caching and errors.
- [Verification results](docs/verification.md) — tested versions, interrupt behavior and evidence limits.
- [Technical design](docs/design.md) and [implementation tickets](docs/issues/).

Run the offline suite from the ComfyUI root using its Python environment:

```sh
.venv/bin/python custom_nodes/comfyui-typesafe/tests/run.py
```

Tests use fixtures and loopback HTTP; they make no paid API calls. This package
has its own Git repository, separate from the host ComfyUI checkout.
