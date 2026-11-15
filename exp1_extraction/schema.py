from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import re

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_date_str(v):
    if v is None:
        return v
    if not DATE_RE.match(v):
        raise ValueError(f"日期格式错误: {v}")
    return v


class OtherDate(BaseModel):
    type: str
    date: Optional[str] = None
    description: Optional[str] = None

    _v = field_validator("date")(classmethod(lambda cls, v: _check_date_str(v)))


class RegistrationFee(BaseModel):
    category: str
    amount: float
    currency: str
    stage: Optional[str] = None
    valid_until: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def _amount_nonneg(cls, v):
        if v < 0:
            raise ValueError("amount 不能为负")
        return v


class RegistrationPolicy(BaseModel):
    student_eligibility: Optional[str] = None
    student_proof_required: Optional[str] = None
    early_bird_condition: Optional[str] = None
    fee_includes: List[str] = Field(default_factory=list)
    fee_excludes: List[str] = Field(default_factory=list)


class Contact(BaseModel):
    email: Optional[str] = None
    website: Optional[str] = None


class ConferenceInfo(BaseModel):
    conference_name: Optional[str] = None
    conference_full_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    submission_deadline: Optional[str] = None
    other_dates: List[OtherDate] = Field(default_factory=list)
    registration_fee: List[RegistrationFee] = Field(default_factory=list)
    registration_policy: RegistrationPolicy = Field(default_factory=RegistrationPolicy)
    organizer: Optional[str] = None
    contact: Contact = Field(default_factory=Contact)

    @field_validator("start_date", "end_date", "submission_deadline")
    @classmethod
    def _check_date(cls, v):
        return _check_date_str(v)