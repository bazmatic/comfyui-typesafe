from dataclasses import dataclass
import math

from .errors import ConfigurationError, ProviderProtocolError


def probability(value, error=ProviderProtocolError):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1 or not math.isfinite(value):
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


@dataclass(frozen=True)
class GuardDecision:
    should_stop: bool
    probability: float
    threshold: float
    metadata: DecisionMetadata


def installed_name(value):
    from pathlib import PurePosixPath, PureWindowsPath
    nonblank(value, "LoRA name")
    if (PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive
            or PureWindowsPath(value).is_absolute()
            or ".." in value.replace("\\", "/").split("/") or "\0" in value):
        raise ConfigurationError("LoRA name must be an installed relative name, not an absolute or parent path.")
    return value


def lora_strength(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not -100 <= value <= 100 or not math.isfinite(value)):
        raise ConfigurationError("LoRA strengths must be finite numbers from -100 to 100.")
    return value


@dataclass(frozen=True)
class LoraCandidate:
    name: str
    description: str
    strength_model: float = 1.0
    strength_clip: float = 1.0
    trigger_words: str = ""

    def __post_init__(self):
        installed_name(self.name)
        nonblank(self.description, "LoRA description")
        lora_strength(self.strength_model)
        lora_strength(self.strength_clip)
        if not isinstance(self.trigger_words, str):
            raise ConfigurationError("Trigger words must be text.")


@dataclass(frozen=True)
class ChoiceQuestion:
    instructions: str
    criteria: tuple[tuple[str, str], ...]

    def __post_init__(self):
        nonblank(self.instructions, "Choice instructions")
        if (type(self.criteria) is not tuple or not self.criteria
                or any(type(pair) is not tuple or len(pair) != 2
                       or any(not isinstance(v, str) or not v.strip() for v in pair)
                       for pair in self.criteria)
                or len({key for key, _ in self.criteria}) != len(self.criteria)):
            raise ConfigurationError("Choice criteria must contain unique named options.")


@dataclass(frozen=True)
class ChoiceJudgment:
    winner_id: str
    probabilities: tuple[tuple[str, float], ...]
    confidence: float
    metadata: DecisionMetadata

    def __post_init__(self):
        probability(self.confidence)
        if (not isinstance(self.metadata, DecisionMetadata)
                or type(self.probabilities) is not tuple or not self.probabilities
                or any(type(pair) is not tuple or len(pair) != 2
                       or not isinstance(pair[0], str) for pair in self.probabilities)):
            raise ProviderProtocolError("Invalid Choice judgment record.")
        values = dict(self.probabilities)
        if len(values) != len(self.probabilities) or not isinstance(self.winner_id, str) or self.winner_id not in values:
            raise ProviderProtocolError("Invalid Choice option IDs.")
        for value in values.values():
            probability(value)
        if abs(math.fsum(values.values()) - 1) > 0.01:
            raise ProviderProtocolError("Choice probabilities must sum to one within 0.01.")
        if max(values.values()) - values[self.winner_id] > 1e-6:
            raise ProviderProtocolError("Choice winner is not maximal.")

    def validate_options(self, option_ids):
        self.__post_init__()
        if set(key for key, _ in self.probabilities) != set(option_ids):
            raise ProviderProtocolError("Choice response must cover exactly the requested options.")


@dataclass(frozen=True)
class LoraSelection:
    candidate_or_none: LoraCandidate | None
    reason: str
    raw_judgment: ChoiceJudgment

    def __post_init__(self):
        if not isinstance(self.raw_judgment, ChoiceJudgment):
            raise ProviderProtocolError("Invalid selection judgment.")
        self.raw_judgment.__post_init__()
        if self.candidate_or_none is not None:
            validate_candidate(self.candidate_or_none)
            if self.reason != "selected":
                raise ConfigurationError("A matched selection must have reason selected.")
        elif self.reason not in ("ambiguous", "no_match", "low_confidence"):
            raise ConfigurationError("An absent selection must have an abstention reason.")


def validate_candidate(candidate):
    if not isinstance(candidate, LoraCandidate):
        raise ConfigurationError("Expected a TypeSafe LoRA Candidate record.")
    candidate.__post_init__()
    return candidate


Question = NoulQuestion | ChoiceQuestion
Judgment = NoulJudgment | ChoiceJudgment


def validate_selection(selection):
    if not isinstance(selection, LoraSelection):
        raise ConfigurationError("Expected a TypeSafe LoRA Selection record.")
    selection.__post_init__()
    return selection
