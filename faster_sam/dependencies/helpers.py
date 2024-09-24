def build_messages_attributes(attributes: dict[str, str]) -> dict[str, dict[str, str]]:
    attrs = {}

    for key, value in attributes.items():
        if isinstance(value, str):
            attrs[key] = {"stringValue": value, "dataType": "String"}
        elif isinstance(value, (int, float)):
            attrs[key] = {"stringValue": str(value), "dataType": "Number"}
        else:
            raise TypeError(f"{value} of type {type(value).__name__} is not supported")

    return attrs
