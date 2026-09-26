from comfy_api.latest import ComfyExtension

from .decisions import DecisionEngine
from .gateway import TypeSafeHttpGateway
from .nodes import TypeSafeTextGuard


class TypeSafeExtension(ComfyExtension):
    async def get_node_list(self):
        return [TypeSafeTextGuard]


async def comfy_entrypoint():
    TypeSafeTextGuard.engine = DecisionEngine(TypeSafeHttpGateway())
    return TypeSafeExtension()
