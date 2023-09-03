# Continuous Integration Example

This repository contains an example of a continious integration pipeline for a FastAPI application.

## Development

Create a Python virtual environment and install the required dependencies:

```shell
$ python3 -m venv venv
$ source venv/bin/activate
$ pip install -e .[dev]
$ pre-commit install
```

## Run

### Python

```shell
$ python -m src.main
```

### Docker

```shell
$ docker run --rm -it -p 80:8080 $(docker build -q .)
```

### Kubernetes

#### Requirements

- [KinD](https://kind.sigs.k8s.io)
- [Helm](https://helm.sh)
- [Docker](https://www.docker.com)

#### Install

```shell
$ python -m scripts.start
```

Go to: **ci-example.local**

### Python

```shell
$ python -m src.main
```

## Test

Install dependencies;

```shell
$ pip install -e .[test]
```

### Unit

Run the Unit tests:

```shell
$ pytest tests/unit
```

### End-to-End

Start [Kubernetes](#kubernetes) environment. Run the End-to-End tests:

```shell
$ pytest tests/e2e
```
