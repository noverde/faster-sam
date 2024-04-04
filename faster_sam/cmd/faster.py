import argparse
import json
import yaml
from typing import Any

from faster_sam.cloudformation import CloudformationTemplate


def output(value: Any, format: str = "text") -> Any:
    if format == "text":
        return yaml.dump(value, sort_keys=False)

    if format == "json":
        return json.dumps(value)


def resources(args) -> None:
    cf = CloudformationTemplate()

    resources = {
        "s3": cf.buckets,
    }

    if "list" in args:
        if args.type is None:
            result = output(cf.template["Resources"], args.output)
        else:
            result = output(resources[args.type], args.output)

        print(result)


def dispatch(args) -> None:
    mapper = {"resources": resources}

    mapper[args.subcommand](args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Faster SAM CLI tool.")

    subparsers = parser.add_subparsers(
        title="subcommand", dest="subcommand", help="Subcommand to execute.", required=True
    )

    resources_parser = subparsers.add_parser("resources", help="Perform operations on resources.")

    resources_parser.add_argument("list", help="List resources.", choices=["list"], type=str)
    resources_parser.add_argument(
        "-t",
        "--type",
        help="Specify the type of resource. Accepted values: 's3'.",
        choices=["s3"],
        type=str,
    )
    resources_parser.add_argument(
        "-o",
        "--output",
        help="Specify the output format. Accepted values: 'text', 'json'. Default: 'text'.",
        default="text",
        choices=["text", "json"],
        type=str,
    )

    args = parser.parse_args()

    dispatch(args)


if __name__ == "__main__":
    main()
