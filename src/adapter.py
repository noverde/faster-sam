from fastapi import FastAPI


class SAM:
    def __init__(self, app: FastAPI) -> None:
        self.app = app
