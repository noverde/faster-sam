import argparse
import json
from typing import Any, Optional

from faster_sam.cloudformation import CloudformationTemplate


def display(title: str, message: str) -> None:
    print(title)
    print("=" * len(title))
    print("\n" + message)


def output(format: Optional[str], value: Any) -> Any:
    if format is None:
        return str(value)
    
    if format == "json":
        return json.dumps(value, indent=4)


def resources(args) -> None:
    if args.list:
        template = CloudformationTemplate()
        resources = {}

        if args.type == "s3":
            resources = template.buckets

        result = output(args.output, resources)

        title = f"\nList of Resources ({args.type})"
        display(title, result)


def main():
    parser = argparse.ArgumentParser(description='Faster CLI tool.')
    subparsers = parser.add_subparsers(title='subcommand', dest='subcommand', help='Subcommand to execute.')
   
    resources_parser = subparsers.add_parser('resources', help='Perform operations on resources.')
    
    resources_parser.add_argument('list', help='List resources.')
    resources_parser.add_argument('--type', help='Specify the type of resource.')
    resources_parser.add_argument('--output', help='Specify the output format.')    

    args = parser.parse_args()

    if args.subcommand == "resources":
        resources(args)


if __name__ == "__main__":
    main()
