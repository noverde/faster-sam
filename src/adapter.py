from typing import Optional

from fastapi import FastAPI

from cloudformation import Template


class SAM(FastAPI):
    def __init__(self, template: Optional[str] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cloudformation = Template(template)
