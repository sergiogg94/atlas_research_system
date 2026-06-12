from typing import Protocol
from abc import ABC, abstractmethod


class PromptTemplate(ABC):
    """Base class for all prompt templates in the system."""

    @property
    @abstractmethod
    def template(self) -> str:
        """The raw prompt template string."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version of this prompt (e.g. '1.0.0')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this prompt does."""
        ...

    def format(self, **kwargs: str) -> str:
        """Format the template with the given keyword arguments."""
        return self.template.format(**kwargs)