# Faster-SAM

> Adapter for FastAPI to run APIs built using AWS SAM

![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)
[![Tests](https://github.com/noverde/faster-sam/actions/workflows/tests.yml/badge.svg)](https://github.com/noverde/faster-sam/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/example.svg)](https://badge.fury.io/py/example)

## About The Project

`Faster-SAM` is a library designed to integrate APIs built using the AWS Serverless Application Model (SAM) with FastAPI, enabling developers to run their AWS SAM applications outside of the AWS environment. FastAPI, known for its high-performance and easy-to-use framework for building APIs with Python, gains compatibility with AWS SAM through this specialized adapter.

### Dependencies

- Python 3.8+
- FastAPI
- PyYaml

## Installation

To install the `Faster-SAM` library, use the following pip command:

```sh
pip install faster-sam
```

## Usage example

Add this code exemple in your project:

```python
from fastapi import SAM
from faster_sam import FastAPI

app = FastAPI()

sam = SAM()
sam.configure_api(app)
```
