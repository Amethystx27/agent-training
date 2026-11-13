from __future__ import annotations

import math
import re
from datetime import date
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]

DateType = Literal[
    "abstract_registration",
    "acceptance_notification",
    "camera_ready",
    "early_bird_registration",
    "other",
]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields instead of silently dropping them."""

    model_config = ConfigDict(extra="forbid")


class OtherDate(StrictModel):
    type: DateType
    date: date


class RegistrationFee(StrictModel):
    category: NonEmptyText
    amount: float = Field(gt=0)
    currency: str

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_be_positive_json_number(cls, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("amount 必须是 JSON 数字，不能是字符串或布尔值")
        if not math.isfinite(value):
            raise ValueError("amount 必须是有限数字")
        if value <= 0:
            raise ValueError("amount 必须大于 0")
        return float(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("currency 必须是字符串")
        currency = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency 必须是三位字母币种代码，例如 USD")
        return currency


class ConferenceInfo(StrictModel):
    # Fields are required to be present, but their values may be null.
    conference_name: NonEmptyText | None
    conference_full_name: NonEmptyText | None
    start_date: date | None
    end_date: date | None
    location: NonEmptyText | None
    topics: list[NonEmptyText] | None
    submission_deadline: date | None
    other_dates: list[OtherDate] | None
    registration_fee: list[RegistrationFee] | None
    organizer: NonEmptyText | None

    @field_validator("topics")
    @classmethod
    def topics_must_be_unique(
        cls, value: list[NonEmptyText] | None
    ) -> list[NonEmptyText] | None:
        if value is None:
            return None
        normalized = [topic.casefold() for topic in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("topics 中不能包含重复主题")
        return value

    @field_validator("other_dates")
    @classmethod
    def dates_must_be_unique(
        cls, value: list[OtherDate] | None
    ) -> list[OtherDate] | None:
        if value is None:
            return None
        keys = [(item.type, item.date) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("other_dates 中不能包含重复的日期类型和日期")
        return value

    @field_validator("registration_fee")
    @classmethod
    def fee_categories_must_be_unique(
        cls, value: list[RegistrationFee] | None
    ) -> list[RegistrationFee] | None:
        if value is None:
            return None
        categories = [item.category.casefold() for item in value]
        if len(categories) != len(set(categories)):
            raise ValueError("registration_fee 中不能包含重复的收费类别")
        return value

    @model_validator(mode="after")
    def validate_date_order(self) -> ConferenceInfo:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date 不能晚于 end_date")
        return self
