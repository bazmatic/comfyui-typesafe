from dataclasses import dataclass
import math

from .errors import ConfigurationError, ProviderProtocolError


def probability(value, error=ProviderProtocolError):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise error("Expected a finite probability in [0, 1].")
    return float(value)


def nonblank(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} must be nonblank text.")
    return value


@dataclass(frozen=True)
class DecisionMetadata:
    requested_model: str
    returned_model: str
    input_tokens: int
    output_tokens: int

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() for v in (self.requested_model, self.returned_model)):
            raise ProviderProtocolError("Invalid judgment model metadata.")
        if any(type(v) is not int or v < 0 for v in (self.input_tokens, self.output_tokens)):
            raise ProviderProtocolError("Invalid judgment token metadata.")


@dataclass(frozen=True)
class NoulQuestion:
    instructions: str


@dataclass(frozen=True)
class NoulJudgment:
    probability: float
    metadata: DecisionMetadata

    def __post_init__(self):
        probability(self.probability)
        if not isinstance(self.metadata, DecisionMetadata):
            raise ProviderProtocolError("Invalid judgment metadata.")


# Closed aliases extended with Choice in the Selector slice.
Question = NoulQuestion
Judgment = NoulJudgment


@dataclass(frozen=True)
class GuardDecision:
    should_stop: bool
    probability: float
    threshold: float
    metadata: DecisionMetadata
