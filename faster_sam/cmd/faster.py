import argparse
import json
from enum import Enum

import yaml

from faster_sam.cloudformation import CloudformationTemplate


class OutputFormat(Enum):
    JSON = "json"
    TEXT = "text"


formatters = {
    OutputFormat.JSON: json.dumps,
    OutputFormat.TEXT: lambda v: yaml.dump(v, sort_keys=False),
}


def resource_list(args: argparse.Namespace) -> None:
    cf = CloudformationTemplate(args.file)
    resources = cf.template["Resources"]

    if args.type is not None:
        resources = getattr(cf, args.type)

        if args.type in ("functions", "buckets", "queues"):
            resources = {key: value.resource for key, value in resources.items()}
            
    if resources:
        formatter = formatters[OutputFormat(args.output)]
        print(formatter(resources))


def main() -> None:
    parser = argparse.ArgumentParser(description="Faster SAM CLI tool.")
    subparser = parser.add_subparsers(title="Subcommands", required=True)

    rsc_parser = subparser.add_parser("resources", help="resource commands.")
    rsc_subparser = rsc_parser.add_subparsers(required=True)

    rsc_list_parser = rsc_subparser.add_parser("list", help="list resources.")
    rsc_list_parser.set_defaults(func=resource_list)
    rsc_list_parser.add_argument(
        "-f",
        "--file",
        default="template.yml",
        help="path to the CloudFormation template file. default: %(default)s.",
    )
    rsc_list_parser.add_argument(
        "-t",
        "--type",
        choices=["buckets", "functions", "gateways", "queues"],
        help="filter by resource type. accepted values: %(choices)s.",
    )
    rsc_list_parser.add_argument(
        "-o",
        "--output",
        choices=[e.value for e in OutputFormat],
        default=OutputFormat.TEXT.value,
        help="output format. accepted values: %(choices)s. default: %(default)s.",
    )

    args = parser.parse_args()
    args.func(args)
