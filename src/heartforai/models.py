"""Data models for insurance policy holders using SQLModel."""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class PolicyHolder(SQLModel, table=True):
    """Model representing an insurance policy holder's policy data."""

    id: Optional[int] = Field(default=None, primary_key=True)
    policy_id: str = Field(index=True, description="9-digit policy identifier")
    product_id: str = Field(description="4-digit product identifier")
    product_name: str = Field(description="Name of the insurance product")
    coverage_desc: str = Field(description="Type of coverage (e.g., Fire, Theft)")
    policy_start_dt: datetime = Field(description="Policy start date")
    policy_end_dt: datetime = Field(description="Policy end date")
    premium_amt: float = Field(description="Premium amount")
    language: str = Field(description="Language preference (NL, FR, EN)")
    postal_code: str = Field(description="4-digit Belgian postal code")

    class Config:
        json_schema_extra = {
            "example": {
                "policy_id": "900100000",
                "product_id": "2178",
                "product_name": "Home Insurance",
                "coverage_desc": "Fire, Theft",
                "policy_start_dt": "2025-01-01",
                "policy_end_dt": "2026-01-01",
                "premium_amt": 450.00,
                "language": "NL",
                "postal_code": "2000"
            }
        }
