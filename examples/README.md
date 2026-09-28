# Example workflows

Open either JSON file in ComfyUI using **Workflow → Open**, or drag it onto the
canvas. These are visual workflow files, not API prompt files. Install this
extension and restart ComfyUI first; see [setup](../README.md).

Both examples require an installed checkpoint. Replace
`CHOOSE_INSTALLED_CHECKPOINT.safetensors` in Load Checkpoint. The 512×512 latent
and sampling settings are illustrative; adjust them for your checkpoint.
No model weights or credentials are included. Set `TYPESAFE_API_KEY` in the
ComfyUI server environment before running Guard or Selector.

## Guard before sampling

[guard-before-sampling.json](guard-before-sampling.json) connects Guard's text
output to positive CLIP encoding, then KSampler. Passing text reaches sampling;
rejection prevents that dependent branch from running. Checkpoint loading and
other independent work can happen before rejection.

Edit the text and condition to suit your use case. Preview Any nodes display the
probability and decision JSON on successful evaluation. Rejection raises an error
with probability and threshold instead of normal outputs. To inspect only a
successful judgment, select its preview and use **Execute to selected output
nodes**; this avoids the checkpoint/sampling branch. Change `refresh_id` to request
a new judgment for unchanged inputs.

## Select and apply one LoRA

[select-and-apply-lora.json](select-and-apply-lora.json) connects two Candidates to
Selector, and its authoritative selection to Apply Selected LoRA. Replace both
`CHOOSE_*_LORA.safetensors` placeholders with different installed LoRAs compatible
with your checkpoint. Edit descriptions, strengths and trigger words to match
those files. The example strengths are model 0.8 and CLIP 0.7.

Apply feeds the sampler and both text encoders. A selected candidate applies its
exact stored settings; none preserves the original MODEL and CLIP. The growing
Selector input exposes a spare socket for another Candidate. Preview Any nodes
show decision JSON and raw confidence, including the filename mapping and reason.

The visible String Concatenate node explicitly appends selected trigger words to
the base text with a space. This is an example of opting into composition. To
omit triggers, connect the original multiline text directly to positive CLIP
encoding. A none result supplies empty triggers (the concatenator retains a
trailing separator).

Both files were saved, closed and reopened in the tested frontend. Offline tests
execute their topology with lightweight checkpoint/sampling fixtures and cover
pass/reject and selected/none outcomes. Real rendering and live judgment quality
have not been evaluated. See [verification details](../docs/verification.md).
