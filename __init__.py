from comfy_api.latest import ComfyExtension

from .decisions import DecisionEngine
from .gateway import TypeSafeHttpGateway
from .nodes import TypeSafeTextGuard, TypeSafeLoraCandidate, TypeSafeLoraSelect, TypeSafeLoraApply
from .lora_runtime import ComfyLoraRuntime


class TypeSafeExtension(ComfyExtension):
    async def get_node_list(self):
        return [TypeSafeTextGuard, TypeSafeLoraCandidate, TypeSafeLoraSelect, TypeSafeLoraApply]


async def comfy_entrypoint():
    TypeSafeTextGuard.engine = DecisionEngine(TypeSafeHttpGateway())
    TypeSafeLoraCandidate.runtime = ComfyLoraRuntime()
    TypeSafeLoraSelect.runtime = TypeSafeLoraCandidate.runtime
    TypeSafeLoraSelect.engine = TypeSafeTextGuard.engine
    TypeSafeLoraApply.runtime = TypeSafeLoraCandidate.runtime
    return TypeSafeExtension()
