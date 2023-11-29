from typing import Optional

from fastapi import FastAPI

import cloudformation


class SAM(FastAPI):
    def __init__(self, template: Optional[str] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cloudformation = cloudformation.Template(template)
