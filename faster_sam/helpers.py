from typing import Dict


def build_message_attributes(attributes: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    attrs = {}

    for key, value in attributes.items():
        if isinstance(value, str):
            attrs[key] = {"stringValue": value, "dataType": "String"}
        elif isinstance(value, (int, float)):
            attrs[key] = {"stringValue": str(value), "dataType": "Number"}
        elif isinstance(value, bytes):
            attrs[key] = {"BinaryValue": str(value), "dataType": "Binary"}
        else:
            raise TypeError(f"{value} of type {type(value).__name__} is not supported")

    return attrs
