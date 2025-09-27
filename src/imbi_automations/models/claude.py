import enum

import pydantic


class AgentRunResult(enum.Enum):
    success = 'success'
    failure = 'failure'


class AgentRun(pydantic.BaseModel):
    result: AgentRunResult
    message: str | None = None
    errors: list[str] = pydantic.Field(default_factory=list)
