# Verification record

Verified on 2026-09-28 with ComfyUI 0.11.1, backend commit
`3c1a1a2df82fc6c7aa20a3c8301d1c632e1a1d87`, frontend package 1.37.11,
Python 3.10.13 and PyTorch 2.10.0 in CPU mode. This records one tested environment;
it does not establish support for historical ComfyUI versions.

## Offline host acceptance

Run the command in [the README](../README.md#offline-validation). All 38 tests pass.
Tests use the real host schemas and prompt executor, fake decision gateways,
temporary LoRA metadata and mocked heavy weight operations. They cover the four
registrations, validation, custom sockets, Autogrow packing, mapped execution,
decision policies, diagnostics, refresh/cache behavior and file replacement or
removal. Transport tests use a loopback HTTP server and fake credentials.

The exported example graphs themselves execute through the host with only costly
checkpoint, encoding, sampling, decoding and saving operations replaced by
fixtures. Passing Guard text reaches the sampler; rejection prevents positive
encoding and sampling. Selected LoRA settings reach the loader unchanged, and
none returns the original MODEL/CLIP without loading. Explicit trigger composition
and Preview Any decision JSON are checked in these graphs.

## Browser acceptance

Chrome loaded the package through an isolated CPU ComfyUI server. Both visual
examples were opened, saved, closed and reopened with their widget values and
connections intact. The two-Candidate graph displayed the custom sockets, spare
Autogrow candidate input, Apply wiring and explicit trigger concatenation. Earlier
integration checks also exercised adding growing inputs and save/reopen.

A temporary server harness substituted only the decision gateway to display
successful Guard JSON in Preview Any through **Execute to selected output nodes**.
The displayed probability was 0.1 and metadata identified `offline-browser-fixture`.
This harness is not part of the shipped package. No paid requests were made, and
no real checkpoint or LoRA weights were available for a full browser render.

## Interrupt timing

The real prompt executor evaluated Guard through the real HTTP transport against
a deliberately blocked loopback response. The test set `nodes.interrupt_processing`
to true, the same host flag used by ComfyUI's Interrupt endpoint. It did not cancel
the pending HTTP operation: after 150 ms the prompt was still waiting.

When the fixture released its response after that wait, the executor reported
`execution_interrupted` before running the dependent consumer (about 0.16 seconds
after the interrupt). When the response stayed blocked, a configured one-second
request deadline produced `execution_error` at about 1.00 second, again with no
dependent execution. These are local fixture timings, not network latency promises.

Set `TYPESAFE_TIMEOUT_SECONDS` to bound this wait (1–120 seconds, default 30).
Transport-level task cancellation is separately tested for cleanup, but this host's
interrupt flag does not immediately cancel an in-flight request. Guard rejection
also does not undo completed work, stop independent branches, clear queued prompts
or interrupt other users.

## Remaining evidence limits

These checks establish offline integration behavior, not TypeSafe semantic quality,
threshold calibration, real model/LoRA compatibility or image quality. The opt-in
live evaluation in ticket 06 remains separate. Users must choose compatible weights,
inspect core warnings and calibrate thresholds for their own data. No credentials
or provider response bodies are stored in the example files.
