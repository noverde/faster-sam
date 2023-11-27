from fastapi import FastAPI, routing


class SAM(FastAPI):
    ...


class APIRoute(routing.APIRoute):
    def __init__(self, endpoint, *args, **kwargs):
        super().__init__(endpoint=endpoint, *args, **kwargs)
