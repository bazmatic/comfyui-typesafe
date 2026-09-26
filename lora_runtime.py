"""Installed LoRA access and application through the core loader."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import folder_paths

from .domain import LoraCandidate, installed_name, validate_candidate
from .errors import ConfigurationError, LoraApplicationError


@dataclass(frozen=True)
class LoraFingerprint:
    resolved_path: str
    device: int
    inode: int
    size: int
    mtime_ns: int


class LoraRuntime(Protocol):
    def list_names(self) -> tuple[str, ...]: ...

    def validate_file(self, name: str) -> None: ...

    def fingerprint(self, name: str) -> LoraFingerprint: ...


    def apply(self, model, clip, candidate: LoraCandidate) -> tuple: ...


class ComfyLoraRuntime:
    def list_names(self) -> tuple[str, ...]:
        try:
            return tuple(folder_paths.get_filename_list("loras"))
        except OSError as exc:
            raise ConfigurationError("The LoRA library is unavailable. Check configured folders and refresh the node list.") from exc

    def _resolve(self, name: str) -> Path:
        names = self.list_names()
        if not names:
            raise ConfigurationError("No LoRAs are installed. Add a LoRA to a configured ComfyUI LoRA folder and refresh the node list.")
        installed_name(name)
        if name not in names:
            raise ConfigurationError("Choose an exact installed LoRA name from the node's list.")
        path = folder_paths.get_full_path("loras", name)
        if path is None:
            raise ConfigurationError("The selected LoRA is missing. Refresh the node list and choose an installed file.")
        try:
            resolved = Path(path).resolve(strict=True)
            if not resolved.is_file():
                raise OSError("Not a file")
            return resolved
        except (OSError, RuntimeError) as exc:
            raise ConfigurationError("The selected LoRA is unavailable. Check the file and refresh the node list.") from exc

    def validate_file(self, name: str) -> None:
        self.fingerprint(name)

    def fingerprint(self, name: str) -> LoraFingerprint:
        path = self._resolve(name)
        try:
            stat = path.stat()
        except OSError as exc:
            raise ConfigurationError("The selected LoRA is unavailable. Check the file and refresh the node list.") from exc
        return LoraFingerprint(str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)

    def apply(self, model, clip, candidate: LoraCandidate) -> tuple:
        validate_candidate(candidate)
        try:
            self.validate_file(candidate.name)
        except ConfigurationError as exc:
            raise LoraApplicationError(
                "The accepted LoRA is unavailable. Restore the file or rerun selection with an installed candidate."
            ) from exc
        # Import lazily: registration and metadata nodes never initialize a loader.
        from nodes import LoraLoader
        from comfy.model_management import InterruptProcessingException
        try:
            # The core loader caches weights by filename, so never retain it across runs.
            return LoraLoader().load_lora(model, clip, candidate.name,
                                          candidate.strength_model, candidate.strength_clip)
        except InterruptProcessingException:
            raise
        except Exception as exc:
            raise LoraApplicationError(
                f"Could not apply the accepted LoRA. Check its file and base-model compatibility. Core loader: {exc}"
            ) from exc
