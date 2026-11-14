from collections.abc import AsyncGenerator
from typing import Protocol

from agent_runtime.domain.a2a.a2a_task_request import A2aTaskRequest
from agent_runtime.domain.a2a.task_update import TaskUpdate


class RunA2aTaskPort(Protocol):
    def run(self, request: A2aTaskRequest) -> AsyncGenerator[TaskUpdate]: ...
