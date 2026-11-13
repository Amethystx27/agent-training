from __future__ import annotations

from datetime import date
from itertools import product
from typing import Literal

from pydantic import Field, model_validator

from schemas import NonEmptyText, RegistrationFee, StrictModel


FeeCategory = Literal[
    "regular_author",
    "student_author",
    "non_author_participant",
]
FeeStage = Literal["early_bird", "regular"]

EXPECTED_CATEGORIES = (
    "regular_author",
    "student_author",
    "non_author_participant",
)
EXPECTED_STAGES = ("early_bird", "regular")
EXPECTED_FEE_COMBINATIONS = set(product(EXPECTED_CATEGORIES, EXPECTED_STAGES))


class AdvancedRegistrationFee(RegistrationFee):
    category: FeeCategory
    stage: FeeStage
    discount_deadline: date | None


class RegistrationPolicy(StrictModel):
    student_eligibility: NonEmptyText
    student_proof: list[NonEmptyText] = Field(min_length=1)
    registration_conditions: list[NonEmptyText] = Field(min_length=1)
    included_services: list[NonEmptyText] = Field(min_length=1)
    excluded_expenses: list[NonEmptyText] = Field(min_length=1)


class AdvancedConferenceInfo(StrictModel):
    conference_name: NonEmptyText
    conference_full_name: NonEmptyText
    start_date: date
    end_date: date
    location: NonEmptyText
    topics: list[NonEmptyText] = Field(min_length=1)
    submission_deadline: date
    acceptance_notification: date
    camera_ready_deadline: date
    early_bird_registration_deadline: date
    registration_fees: list[AdvancedRegistrationFee]
    registration_policy: RegistrationPolicy

    @model_validator(mode="after")
    def validate_conference_dates(self) -> AdvancedConferenceInfo:
        if self.start_date > self.end_date:
            raise ValueError("start_date 不能晚于 end_date")
        if not (
            self.submission_deadline
            <= self.acceptance_notification
            <= self.camera_ready_deadline
            <= self.start_date
        ):
            raise ValueError("投稿、录用、最终论文和会议日期顺序不正确")
        if self.early_bird_registration_deadline > self.start_date:
            raise ValueError("早鸟注册截止日期不能晚于会议开始日期")
        return self

    @model_validator(mode="after")
    def validate_fee_matrix(self) -> AdvancedConferenceInfo:
        actual = {
            (fee.category, fee.stage)
            for fee in self.registration_fees
        }
        if len(actual) != len(self.registration_fees):
            raise ValueError("registration_fees 中存在重复的类别和收费阶段")

        missing = EXPECTED_FEE_COMBINATIONS - actual
        extra = actual - EXPECTED_FEE_COMBINATIONS
        if missing or extra:
            raise ValueError(
                "registration_fees 必须完整覆盖三类参会者与两个收费阶段；"
                f"缺少={sorted(missing)}，多出={sorted(extra)}"
            )

        currencies = {fee.currency for fee in self.registration_fees}
        if len(currencies) != 1:
            raise ValueError("同一会议的所有注册费用必须使用一致币种")

        for category in EXPECTED_CATEGORIES:
            early = next(
                fee
                for fee in self.registration_fees
                if fee.category == category and fee.stage == "early_bird"
            )
            regular = next(
                fee
                for fee in self.registration_fees
                if fee.category == category and fee.stage == "regular"
            )
            if early.amount >= regular.amount:
                raise ValueError(f"{category} 的早鸟价必须低于普通价")
            if early.discount_deadline != self.early_bird_registration_deadline:
                raise ValueError(
                    f"{category} 的早鸟价截止日期与顶层早鸟截止日期不一致"
                )
            if regular.discount_deadline is not None:
                raise ValueError(
                    f"{category} 的普通价不应设置早鸟优惠截止日期"
                )
        return self
