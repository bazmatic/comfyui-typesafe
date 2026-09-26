from dataclasses import asdict
import json

from comfy_api.latest import io

from .decisions import DEFAULT_CONDITION
from .errors import ConfigurationError, GuardRejected


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
