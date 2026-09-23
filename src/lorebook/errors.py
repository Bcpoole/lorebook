"""Application errors shared by feature services and transport adapters."""


class LorebookError(Exception):
    """Base class for expected application failures."""


class InvalidRequestError(LorebookError):
    """Raised when a feature cannot execute with the supplied state."""


class GenerationUnavailableError(LorebookError):
    """Raised when an external generation service is unavailable."""


class ArtifactAssemblyError(LorebookError):
    """Raised when generated content cannot form a valid artifact."""
