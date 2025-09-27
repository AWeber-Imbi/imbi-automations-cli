import pydantic


class BaseModel(pydantic.BaseModel):
    """Base model for GitHub API responses."""

    def __hash__(self) -> int:
        return hash(self.model_dump_json())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self.model_dump() == other.model_dump()

    model_config = pydantic.ConfigDict(extra='ignore')
