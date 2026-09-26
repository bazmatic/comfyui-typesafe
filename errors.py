class ConfigurationError(ValueError):
    """Invalid local configuration; no decision was made."""


class ProviderUnavailable(RuntimeError):
    """Evaluation could not complete."""


class ProviderProtocolError(RuntimeError):
    """The provider did not return a valid judgment."""


class GuardRejected(RuntimeError):
    def __init__(self, probability, threshold):
        self.probability = probability
        self.threshold = threshold
        super().__init__(f"Text Guard stopped this prompt: probability {probability:g} >= threshold {threshold:g}.")


class LoraApplicationError(RuntimeError):
    """An accepted LoRA could not be applied."""
