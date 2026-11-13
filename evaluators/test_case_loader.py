from pathlib import Path

import yaml
from pydantic import ValidationError

from schemas.test_case import TestCase


def load_test_case(file_path: str | Path) -> TestCase:
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Test case file not found: {path}"
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as error:
        raise ValueError(
            f"Invalid YAML in {path}: {error}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError(
            f"Test case must be a YAML mapping: {path}"
        )

    try:
        return TestCase.model_validate(data)
    except ValidationError as error:
        raise ValueError(
            f"Test case validation failed for {path}:\n{error}"
        ) from error


def load_test_cases(directory: str | Path) -> list[TestCase]:
    path = Path(directory)

    if not path.is_dir():
        raise NotADirectoryError(
            f"Test case directory not found: {path}"
        )

    files = sorted(path.glob("*.yaml"))

    if not files:
        raise ValueError(
            f"No YAML test cases found in {path}"
        )

    return [load_test_case(file) for file in files]
