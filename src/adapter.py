from typing import Optional

from fastapi import FastAPI


class SAM:
    def __init__(self, app: FastAPI, template_path: Optional[str] = None) -> None:
        self.app = app
