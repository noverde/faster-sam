# Faster-SAM

> Adapter for FastAPI to run APIs built using AWS SAM

![Python](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)
[![Upload Python Package](https://github.com/noverde/fastapi-sam-adapter/actions/workflows/publish.yml/badge.svg)](https://github.com/noverde/fastapi-sam-adapter/actions/workflows/publish.yml)
[![PyPI version](https://badge.fury.io/py/example.svg)](https://badge.fury.io/py/example)

<a name="readme-top"></a>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li><a href="#installation">Installation</a></li>
    <li><a href="#usage-example">Usage example</a></li>
  </ol>
</details>

## About The Project

```Faster-SAM``` is a powerful library designed to integrate APIs built using the AWS Serverless Application Model (SAM) with FastAPI, enabling developers to run their AWS SAM applications outside of the AWS environment. FastAPI, known for its high-performance and easy-to-use framework for building APIs with Python, gains compatibility with AWS SAM through this specialized adapter.

### Built With

Key Technologies Employed in the Project.

![Python](https://img.shields.io/badge/Python-black?style=for-the-badge&logo=python)
![PyYaml](https://img.shields.io/badge/PyYaml-black?style=for-the-badge&logo=yaml)
![FastAPI](https://img.shields.io/badge/Fast%20API%20-black?style=for-the-badge&logo=fastapi)
![Uvicorn](https://img.shields.io/badge/Uvicorn-black?style=for-the-badge)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Installation

To install the ```Faster-SAM``` library, use the following pip command:

   ```sh
   pip install faster-sam
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage example

Add this code exemple in your project:

   ```python
   from adapter import SAM
   from fastapi import FastAPI

   app = FastAPI()

   sam = SAM()
   sam.configure_api(app)
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>
