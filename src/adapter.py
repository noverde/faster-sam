from typing import Optional

from fastapi import FastAPI

import cloudformation


class SAM(FastAPI):
    def __init__(self, template: Optional[str] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._cloudformation = cloudformation.load(template)

    def load_routes_from_cloudformation(self):
        functions_list = cloudformation.find_resources(
            self._cloudformation, cloudformation.ResourceType.LAMBDA
        )

        routes = {}

        for function in functions_list:
            for name, conf in function.items():
                properties = conf["Properties"]

                if "Events" not in properties:
                    continue

                events_list = cloudformation.find_events(properties, cloudformation.EventType.API)

                for event in events_list:
                    for event_details in event.values():
                        api = event_details["Properties"]

                        if "RestApiId" in api and "Ref" in api["RestApiId"]:
                            api_gateway = api["RestApiId"]["Ref"]
                        else:
                            api_gateway = "DefaultApiGateway"

                        routes.setdefault(api_gateway, {})

                        code_uri = properties["CodeUri"].replace("/", "")

                        handler = properties["Handler"]

                        endpoint_method = {
                            api["Method"].upper(): {
                                "name": name,
                                "handler": f"{code_uri}.{handler}",
                            }
                        }

                        routes[api_gateway].setdefault(api["Path"], {}).update(endpoint_method)

        return routes
