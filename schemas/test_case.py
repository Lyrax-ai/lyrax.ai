from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ToleranceRule(BaseModel):
    mode: Literal["exact", "numeric_tolerance"] = "exact"
    absolute: float = Field(default=0.0, ge=0)
    relative: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def validate_tolerance(self):
        if self.mode == "exact" and (
            self.absolute != 0 or self.relative != 0
        ):
            raise ValueError(
                "Exact comparison cannot define numeric tolerances."
            )
        return self


class TestCase(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=2)
    capability: str = Field(min_length=1)

    input: Any
    expected_output: Any

    tolerance: ToleranceRule = Field(
        default_factory=ToleranceRule
    )
