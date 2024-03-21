import os
from typing import Dict, Any

from faster_sam.cloudformation import CloudformationTemplate

ENVS_TO_REMOVE = [
    "LOG_LEVEL",
    "ELASTIC_APM_ENVIRONMENT",
    "ELASTIC_APM_LAMBDA_APM_SERVER",
    "ELASTIC_APM_SECRET_TOKEN",
    "ELASTIC_APM_SEND_STRATEGY",
    "ELASTIC_APM_SERVICE_NAME",
    "ENVIRONMENT",
    "AWS_LAMBDA_EXEC_WRAPPER",
]

ENVIRONMENT = os.environ["ENVIRONMENT"]
APP_NAME = os.environ["APP_NAME"]
PROJECT_ID = os.environ["PROJECT_ID"]


class Envs:
    def __init__(self, template: CloudformationTemplate) -> None:
        self._template = template
        self.envs = {**self.local_envs, **self.global_envs}

    @property
    def global_envs(self) -> Dict[str, Any]:
        if not hasattr(self, "_global_envs"):
            self._global_envs = self._template["Globals"]["Function"]["Environment"]["Variables"]
        return self._global_envs

    @property
    def local_envs(self) -> Dict[str, Any]:
        if not hasattr(self, "_local_envs"):
            self._local_envs = {}

            if not self._template.functions:
                return self._local_envs

            for function in self._template.functions.values():
                self._local_envs.update(
                    function["Properties"].get("Environment", {}).get("Variables", {})
                )

            return self._local_envs
        return self._local_envs

    def mapper_variables(self):
        env_mapper = self._template["Mappings"]["Environments"][ENVIRONMENT]

        for env_key, env_value in self.envs.items():
            if "Fn::FindInMap" in env_value:
                for map_key, map_value in env_mapper.items():
                    if map_key == env_value["Fn::FindInMap"][2]:
                        self.envs[env_key] = map_value

    def get_queues(self) -> Dict[str, Any]:
        queue_names = {}

        if not self._template.queues:
            return queue_names

        for queue_key, queue_value in self._template.queues.items():
            queue_names[queue_key] = queue_value["Properties"].get("QueueName", {})

        return queue_names

    def set_queue_envs(self, queues: Dict[str, Any]):
        for env_key, env_value in self.envs.items():
            if "Ref" in env_value:
                for queue_key, queue_name in queues.items():
                    if queue_key in env_value["Ref"]:
                        self.envs[env_key] = f"project/{PROJECT_ID}/topics/{APP_NAME}:{queue_name}"

    def filter_envs(self):
        envs_removed = {}

        for env_key, env_value in self.envs.items():
            if isinstance(env_value, str):
                if "parameters" in env_value or "secrets" in env_value:
                    ENVS_TO_REMOVE.append(env_key)
            elif isinstance(env_value, Dict):
                if env_value.get("Fn::Sub") or env_value.get("Ref"):
                    ENVS_TO_REMOVE.append(env_key)
            if env_key not in ENVS_TO_REMOVE:
                envs_removed[env_key] = env_value

        self.envs = envs_removed
