import pytest

from evaluators.test_case_loader import load_test_case, load_test_cases


def test_load_valid_test_case():
    cases = load_test_cases(
        "test_cases/structured_data_extraction"
    )

    assert len(cases) == 1
    assert cases[0].id == "extraction-001"
    assert cases[0].capability == "structured_data_extraction"
    assert cases[0].expected_output["invoice_number"] == "1042"


def test_reject_missing_required_field(tmp_path):
    path = tmp_path / "missing_field.yaml"

    path.write_text(
        """
id: extraction-002
name: Missing capability
input:
  document: Sample
expected_output:
  result: Sample
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="validation failed"):
        load_test_case(path)


def test_reject_invalid_yaml(tmp_path):
    path = tmp_path / "invalid.yaml"

    path.write_text(
        """
id: [invalid
name: Broken YAML
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid YAML"):
        load_test_case(path)


def test_reject_invalid_tolerance(tmp_path):
    path = tmp_path / "invalid_tolerance.yaml"

    path.write_text(
        """
id: extraction-003
name: Invalid tolerance
capability: structured_data_extraction
input:
  document: Sample
expected_output:
  result: Sample
tolerance:
  mode: exact
  absolute: 0.5
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="validation failed"):
        load_test_case(path)


def test_reject_missing_file(tmp_path):
    path = tmp_path / "does_not_exist.yaml"

    with pytest.raises(FileNotFoundError):
        load_test_case(path)
