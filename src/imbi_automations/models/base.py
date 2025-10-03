"""Base models and common utilities for Pydantic models.

Provides base Pydantic model class with hashability and equality comparison
based on model content, used across all API response models.
"""

import pydantic


class BaseModel(pydantic.BaseModel):
    """Base model with hash and equality support.

    Enables models to be used in sets and as dict keys by implementing
    __hash__ based on JSON serialization and __eq__ based on field values.
    """

    def __hash__(self) -> int:
        return hash(self.model_dump_json())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.model_dump() == other.model_dump()
