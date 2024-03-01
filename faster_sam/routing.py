import logging
from typing import Any, Awaitable, Callable, Dict

from fastapi import Request, Response, routing

from faster_sam.lambda_event import SQS, ApiGateway, ResourceInterface

logger = logging.getLogger(__name__)

Handler = Callable[[Dict[str, Any], Any], Dict[str, Any]]
Endpoint = Callable[[Request], Awaitable[Response]]


def handler(func: Handler, Resource: ResourceInterface) -> Endpoint:
    """
    Returns a wrapper function.

    The returning function converts a request object into a event,
    then the event is passed to the handler function,
    finally the function result is converted to a response object.

    Parameters
    ----------
    func : Handler
        A callable object.

    Returns
    -------
    Endpoint
        An async function, which accepts a single request argument and return a response.
    """

    async def wrapper(request: Request) -> Response:
        caller = Resource(request, endpoint=func)
        result = await caller.call_endpoint()
        logger.debug(f"Result [{result.status_code}]: {result.body.decode()}")
        return result

    return wrapper


def import_handler(path: str) -> Handler:
    """
    Returns a callable object from the given module path.

    Parameters
    ----------
    path : str
        Full module path.

    Returns
    -------
    Handler
        A callable object.
    """
    module_name, handler_name = path.rsplit(".", maxsplit=1)
    module = __import__(module_name, fromlist=(handler_name,))

    return getattr(module, handler_name)


class APIRoute(routing.APIRoute):
    """
    Extends FastAPI Router class used to describe path operations.
    This custom router class receives the endpoint parameter as a string with
    the full module path instead of the actual callable.
    """

    def __init__(self, path: str, endpoint: str, *args, **kwargs):
        """
        Initializes the APIRoute object.

        Parameters
        ----------
        path : str
            HTTP route path.
        endpoint : str
            Full module path.
        """
        handler_path = endpoint
        handler_func = import_handler(handler_path)
        super().__init__(path=path, endpoint=handler(handler_func, ApiGateway), *args, **kwargs)


class QueueRoute(routing.APIRoute):
    """
    Extends FastAPI Router class used to describe path operations.
    This custom router class receives the endpoint parameter as a string with
    the full module path instead of the actual callable.
    """

    def __init__(self, path: str, endpoint: str, *args, **kwargs):
        """
        Initializes the QueueRoute object.

        Parameters
        ----------
        path : str
            HTTP route path.
        endpoint : str
            Full module path.
        """
        handler_path = endpoint
        handler_func = import_handler(handler_path)
        super().__init__(path=path, endpoint=handler(handler_func, SQS), *args, **kwargs)
