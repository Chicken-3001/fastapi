from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from typing import Any, AsyncIterator, Callable, Mapping, TypeVar

from fastapi import FastAPI
from fastapi.dependencies.utils import get_dependant, solve_dependencies
from starlette.requests import HTTPConnection, Request

LifespanDependency = Callable[..., AbstractAsyncContextManager[Any]]
R = TypeVar("R")


# TODO: Improve error messages wheen dependency resolution fails.


class Lifespan:
    def __init__(self) -> None:
        self.dependencies: dict[str, LifespanDependency] = {}

    @asynccontextmanager
    async def __call__(self, app: FastAPI) -> AsyncIterator[Mapping[str, Any]]:
        state: dict[str, Any] = {}

        async with AsyncExitStack() as stack:
            for name, dependency in self.dependencies.items():
                dependant = get_dependant(path="", call=dependency)
                solved_values, *_ = await solve_dependencies(
                    # TODO: Change this usage of an improper `Request` instance.
                    request=Request(
                        scope={
                            "type": "http",
                            "query_string": "",
                            "headers": "",
                            "state": state,
                        }
                    ),
                    dependant=dependant,
                    async_exit_stack=stack,
                )

                state[name] = await stack.enter_async_context(
                    dependency(**solved_values)
                )

            yield state

    def register(
        self, dependency: Callable[..., AsyncIterator[R]]
    ) -> Callable[[HTTPConnection], R]:
        self.dependencies[dependency.__name__] = asynccontextmanager(dependency)

        def path_dependency(connection: HTTPConnection) -> Any:
            return connection.state._state[dependency.__name__]

        return path_dependency
