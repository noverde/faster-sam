from typing import Optional

from fastapi import FastAPI

import cloudformation


class SAM(FastAPI):
    def __init__(self, template: Optional[str] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cloudformation = cloudformation.load(template)
        self._routes = self._build_routes()

    def _build_routes(self):
        return cloudformation.build_routes(self._cloudformation)

    @property
    def cloudformation(self):
        return self._cloudformation

    @property
    def routes(self):
        return self._routes
