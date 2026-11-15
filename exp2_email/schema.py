from typing import List, Optional
from pydantic import BaseModel, Field


class EmailAnalysis(BaseModel):
    sender: Optional[str] = None
    subject: Optional[str] = None
    conference_name: Optional[str] = None
    primary_intent: str
    secondary_intents: List[str] = Field(default_factory=list)
    user_role: Optional[str] = None
    questions: List[str] = Field(default_factory=list)
    extracted_entities: dict = Field(default_factory=dict)
    requires_human_review: bool = False
    review_reason: Optional[str] = None


class ReplyDraft(BaseModel):
    subject: str
    body: str
    requires_human_review: bool = False
    review_reason: Optional[str] = None