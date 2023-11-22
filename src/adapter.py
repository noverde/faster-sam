import yaml
from fastapi import FastAPI


class SAM(FastAPI):
    def read_yml_file(self, path="template.yaml"):
        with open(path) as file:
            return yaml.safe_load(file)
