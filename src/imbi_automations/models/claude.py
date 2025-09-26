import enum

import pydantic


class AgentRunResult(enum.Enum):
    """Claude agent run result."""

    success = 'success'
    failure = 'failure'


class AgentRun(pydantic.BaseModel):
    """Claude agent run."""

    result: AgentRunResult
    message: str
