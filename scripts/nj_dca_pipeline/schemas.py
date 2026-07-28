"""Pydantic schemas for Model A (extract) and Model B (golden records)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


DocType = Literal[
    "permit",
    "alteration",
    "new_construction",
    "addition",
    "demolition",
    "other",
]


class CandidateEntity(BaseModel):
    """High-recall entity from Gemini Flash (Model A)."""

    source_pk: str = Field(..., description="Socrata pk")
    permit_no: Optional[str] = None
    municipality: Optional[str] = None
    county: Optional[str] = None
    block: Optional[str] = None
    lot: Optional[str] = None
    use_group: Optional[str] = None
    permit_type: Optional[str] = None
    permit_date: Optional[str] = None
    process_date: Optional[str] = None
    construction_cost_usd: Optional[float] = None
    square_feet: Optional[float] = None
    project_name_guess: Optional[str] = None
    address_guess: Optional[str] = None
    flagged_uncertain: bool = False
    possible_duplicate_of_pk: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("construction_cost_usd", "square_feet", mode="before")
    @classmethod
    def empty_to_none(cls, v):  # noqa: ANN001
        if v == "" or v is None:
            return None
        return v


class FlashExtractBatch(BaseModel):
    entities: list[CandidateEntity] = Field(default_factory=list)


class GoldenRecord(BaseModel):
    """Deduplicated project/permit golden record from Sonnet (Model B)."""

    golden_id: str
    source_pks: list[str] = Field(default_factory=list)
    permit_numbers: list[str] = Field(default_factory=list)
    municipality: Optional[str] = None
    county: Optional[str] = None
    block: Optional[str] = None
    lot: Optional[str] = None
    use_group: Optional[str] = None
    permit_types: list[str] = Field(default_factory=list)
    earliest_permit_date: Optional[str] = None
    latest_process_date: Optional[str] = None
    construction_cost_usd: Optional[float] = None
    square_feet: Optional[float] = None
    project_name: Optional[str] = None
    address: Optional[str] = None
    doc_type: DocType = "permit"
    merge_reason: Optional[str] = None
    confidence: float = 0.5


class SonnetDedupeBatch(BaseModel):
    records: list[GoldenRecord] = Field(default_factory=list)
    dropped_pks: list[str] = Field(default_factory=list)
    merged_groups: int = 0
