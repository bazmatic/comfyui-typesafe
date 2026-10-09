from dataclasses import asdict, astuple
import json
import re

from comfy_api.latest import io

from .decisions import DEFAULT_CONDITION
from .domain import LoraCandidate, validate_candidate, validate_selection
from .lora_runtime import LoraRuntime
from .errors import ConfigurationError, GuardRejected, LoraApplicationError


class TypeSafeTextGuard(io.ComfyNode):
    engine = None  # Injected by the extension composition root.

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TypeSafeTextGuard", display_name="TypeSafe · Text Guard", category="TypeSafe",
            inputs=[io.String.Input("text", multiline=True),
                    io.String.Input("condition", multiline=True, default=DEFAULT_CONDITION),
                    io.Float.Input("stop_threshold", default=0.5, min=0, max=1),
                    io.String.Input("model", default="jev-latest", advanced=True),
                    io.Int.Input("refresh_id", default=0)],
            outputs=[io.String.Output("text"), io.Float.Output("condition_probability"),
                     io.String.Output("decision_details")],
        )

    @classmethod
    async def execute(cls, text, condition=DEFAULT_CONDITION, stop_threshold=0.5,
                      model="jev-latest", refresh_id=0):
        if type(refresh_id) is not int:
            raise ConfigurationError("Refresh ID must be an integer.")
        decision = await cls.engine.judge_guard(text, condition, stop_threshold, model)
        if decision.should_stop:
            raise GuardRejected(decision.probability, decision.threshold)
        return io.NodeOutput(text, decision.probability, json.dumps(asdict(decision), indent=2))


LoraCandidateSocket = io.Custom("TYPESAFE_LORA_CANDIDATE")


class TypeSafeLoraCandidate(io.ComfyNode):
    runtime: LoraRuntime = None  # Injected by the extension composition root.

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TypeSafeLoraCandidate", display_name="TypeSafe · LoRA Candidate", category="TypeSafe",
            inputs=[io.Combo.Input("lora_name", options=list(cls.runtime.list_names())),
                    io.String.Input("description", multiline=True),
                    io.Float.Input("strength_model", default=1.0, min=-100, max=100),
                    io.Float.Input("strength_clip", default=1.0, min=-100, max=100),
                    io.String.Input("trigger_words", default="", multiline=True)],
            outputs=[LoraCandidateSocket.Output("candidate")],
        )

    @classmethod
    def validate_inputs(cls, lora_name):
        # Override the combo check so empty/stale libraries give actionable errors.
        try:
            cls.runtime.validate_file(lora_name)
        except ConfigurationError as exc:
            return str(exc)
        return True

    @classmethod
    def execute(cls, lora_name, description, strength_model=1.0, strength_clip=1.0, trigger_words=""):
        cls.runtime.validate_file(lora_name)
        candidate = LoraCandidate(lora_name, description, strength_model, strength_clip, trigger_words)
        return io.NodeOutput(candidate)

    @classmethod
    def fingerprint_inputs(cls, lora_name=None, **kwargs):
        if lora_name is None:
            # Linked names are unavailable during the host's cache-key pass.
            return float("nan")
        return astuple(cls.runtime.fingerprint(lora_name))


LoraSelectionSocket = io.Custom("TYPESAFE_LORA_SELECTION")


class TypeSafeLoraSelect(io.ComfyNode):
    engine = None
    runtime: LoraRuntime = None

    @classmethod
    def define_schema(cls):
        template = io.Autogrow.TemplatePrefix(
            input=LoraCandidateSocket.Input("candidate"), prefix="candidate", min=1, max=100)
        return io.Schema(
            node_id="TypeSafeLoraSelect", display_name="TypeSafe · LoRA Selector", category="TypeSafe",
            inputs=[io.String.Input("text", multiline=True),
                    io.Autogrow.Input("candidates", template=template),
                    io.Float.Input("min_confidence", default=0.5, min=0, max=1),
                    io.String.Input("model", default="jev-latest", advanced=True),
                    io.Int.Input("refresh_id", default=0)],
            outputs=[LoraSelectionSocket.Output("selection"), io.String.Output("lora_name"),
                     io.Boolean.Output("has_match"), io.Float.Output("confidence"),
                     io.String.Output("trigger_words"), io.String.Output("decision_details")],
        )

    @classmethod
    async def execute(cls, text, candidates, min_confidence=0.5, model="jev-latest", refresh_id=0):
        if type(refresh_id) is not int:
            raise ConfigurationError("Refresh ID must be an integer.")
        if not isinstance(candidates, dict) or not 1 <= len(candidates) <= 100:
            raise ConfigurationError("Connect between 1 and 100 LoRA candidates.")
        numbered = []
        for key, candidate in candidates.items():
            match = re.fullmatch(r"candidate(0|[1-9][0-9]*)", key) if isinstance(key, str) else None
            if not match or int(match[1]) >= 100:
                raise ConfigurationError("Invalid LoRA candidate socket name.")
            numbered.append((int(match[1]), validate_candidate(candidate)))
        ordered = tuple(candidate for _, candidate in sorted(numbered))
        for candidate in ordered:
            cls.runtime.validate_file(candidate.name)
        selection = await cls.engine.select_lora(text, ordered, min_confidence, model)
        candidate = selection.candidate_or_none
        details = asdict(selection.raw_judgment)
        details.update(reason=selection.reason, has_match=candidate is not None,
                       lora_name=candidate.name if candidate else "",
                       options={f"candidate_{i}": c.name for i, c in enumerate(ordered)},
                       min_confidence=min_confidence)
        return io.NodeOutput(selection, candidate.name if candidate else "", candidate is not None,
                             selection.raw_judgment.confidence, candidate.trigger_words if candidate else "",
                             json.dumps(details, indent=2))


class TypeSafeLoraApply(io.ComfyNode):
    runtime: LoraRuntime = None

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TypeSafeLoraApply", display_name="TypeSafe · Apply Selected LoRA", category="TypeSafe",
            inputs=[io.Model.Input("model"), io.Clip.Input("clip"), LoraSelectionSocket.Input("selection")],
            outputs=[io.Model.Output("model"), io.Clip.Output("clip")],
        )

    @classmethod
    def execute(cls, model, clip, selection):
        candidate = validate_selection(selection).candidate_or_none
        if candidate is None:
            return io.NodeOutput(model, clip)
        return io.NodeOutput(*cls.runtime.apply(model, clip, candidate))

    @classmethod
    def fingerprint_inputs(cls, selection=None, **kwargs):
        if selection is None:
            # A linked selection could come from any cached custom-socket source.
            # Re-execute Apply conservatively; upstream judgments remain cached.
            return float("nan")
        candidate = validate_selection(selection).candidate_or_none
        if candidate is None:
            return ("none",)
        try:
            return astuple(cls.runtime.fingerprint(candidate.name))
        except ConfigurationError as exc:
            raise LoraApplicationError(
                "The accepted LoRA is unavailable. Restore the file or rerun selection with an installed candidate."
            ) from exc
