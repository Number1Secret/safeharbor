"""
Occupation AI Schemas

Input/output models for Treasury Tipped Occupation Code classification.
"""

from pydantic import BaseModel, Field


class TTOCClassificationInput(BaseModel):
    """Input for TTOC classification."""

    employee_id: str = Field(..., description="Unique employee identifier")
    job_title: str = Field(..., min_length=1, max_length=255)
    job_description: str | None = Field(default=None, max_length=5000)
    duties: list[str] = Field(default_factory=list)
    employer_industry: str | None = Field(
        default=None,
        description="Industry: restaurant, hospitality, casino, etc.",
    )
    tip_frequency: str | None = Field(
        default=None,
        description="always|frequently|occasionally|rarely|never",
    )
    hours_per_week: float | None = Field(default=None, ge=0, le=168)
    is_customer_facing: bool | None = None


class TTOCCode(BaseModel):
    """Treasury Tipped Occupation Code definition."""

    code: str = Field(..., pattern=r"^[A-Z0-9]{2,10}$")
    title: str
    description: str
    is_tipped: bool
    typical_tip_percentage: float | None = Field(default=None, ge=0, le=100)
    industry: str


class TTOCClassificationOutput(BaseModel):
    """Output from TTOC classification."""

    employee_id: str

    # Primary classification
    ttoc_code: str = Field(..., description="Assigned TTOC code")
    ttoc_title: str = Field(..., description="Official title for the code")
    ttoc_description: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="AI reasoning for classification")

    # Classification result
    is_tipped_occupation: bool
    typical_tip_percentage: float | None

    # Alternative classifications
    alternative_codes: list[dict] = Field(
        default_factory=list,
        description="Other possible codes with confidence scores",
    )

    # Determinism envelope
    model_id: str
    prompt_version: str
    prompt_hash: str
    response_hash: str

    # Flags
    needs_human_review: bool = Field(
        default=False,
        description="True if confidence is below threshold",
    )
    review_reason: str | None = None


# Treasury Tipped Occupation Codes (subset for MVP)
# Full list would come from IRS publication
TTOC_CODES: list[TTOCCode] = [
    TTOCCode(
        code="12401",
        title="Waiter/Waitress",
        description="Serves food and beverages to patrons at tables in restaurants, cocktail lounges, and other dining establishments",
        is_tipped=True,
        typical_tip_percentage=15.0,
        industry="restaurant",
    ),
    TTOCCode(
        code="12402",
        title="Bartender",
        description="Mixes and serves alcoholic and non-alcoholic drinks to patrons of bar, restaurant, or cocktail lounge",
        is_tipped=True,
        typical_tip_percentage=18.0,
        industry="restaurant",
    ),
    TTOCCode(
        code="12403",
        title="Host/Hostess",
        description="Welcomes guests, manages reservations, and seats customers at restaurants",
        is_tipped=True,
        typical_tip_percentage=5.0,
        industry="restaurant",
    ),
    TTOCCode(
        code="12404",
        title="Busser/Bus Person",
        description="Clears and sets tables, assists waitstaff, and maintains dining area cleanliness",
        is_tipped=True,
        typical_tip_percentage=8.0,
        industry="restaurant",
    ),
    TTOCCode(
        code="12405",
        title="Barback",
        description="Assists bartenders by restocking supplies, cleaning bar area, and preparing garnishes",
        is_tipped=True,
        typical_tip_percentage=10.0,
        industry="restaurant",
    ),
    TTOCCode(
        code="12406",
        title="Food Runner",
        description="Delivers food orders from kitchen to customers' tables",
        is_tipped=True,
        typical_tip_percentage=8.0,
        industry="restaurant",
    ),
    TTOCCode(
        code="12501",
        title="Hotel Bellhop",
        description="Assists hotel guests with luggage, escorts to rooms, and provides information about hotel services",
        is_tipped=True,
        typical_tip_percentage=None,
        industry="hospitality",
    ),
    TTOCCode(
        code="12502",
        title="Hotel Concierge",
        description="Assists hotel guests with reservations, recommendations, and special requests",
        is_tipped=True,
        typical_tip_percentage=None,
        industry="hospitality",
    ),
    TTOCCode(
        code="12503",
        title="Valet Parking Attendant",
        description="Parks and retrieves guests' vehicles at hotels, restaurants, and events",
        is_tipped=True,
        typical_tip_percentage=None,
        industry="hospitality",
    ),
    TTOCCode(
        code="12504",
        title="Room Service Attendant",
        description="Delivers food and beverage orders to hotel guest rooms",
        is_tipped=True,
        typical_tip_percentage=15.0,
        industry="hospitality",
    ),
    TTOCCode(
        code="12601",
        title="Casino Dealer",
        description="Operates table games such as blackjack, poker, roulette, and craps at casinos",
        is_tipped=True,
        typical_tip_percentage=None,
        industry="casino",
    ),
    TTOCCode(
        code="12602",
        title="Casino Cocktail Server",
        description="Serves beverages to casino patrons on the gaming floor",
        is_tipped=True,
        typical_tip_percentage=20.0,
        industry="casino",
    ),
    TTOCCode(
        code="12701",
        title="Hairdresser/Hairstylist",
        description="Cuts, colors, and styles hair for customers at salons",
        is_tipped=True,
        typical_tip_percentage=20.0,
        industry="personal_care",
    ),
    TTOCCode(
        code="12702",
        title="Nail Technician/Manicurist",
        description="Provides manicures, pedicures, and nail treatments",
        is_tipped=True,
        typical_tip_percentage=20.0,
        industry="personal_care",
    ),
    TTOCCode(
        code="12703",
        title="Massage Therapist",
        description="Provides massage therapy services to clients",
        is_tipped=True,
        typical_tip_percentage=20.0,
        industry="personal_care",
    ),
    TTOCCode(
        code="12801",
        title="Taxi/Rideshare Driver",
        description="Transports passengers to destinations via taxi or rideshare service",
        is_tipped=True,
        typical_tip_percentage=15.0,
        industry="transportation",
    ),
    TTOCCode(
        code="12802",
        title="Delivery Driver",
        description="Delivers food, packages, or other goods to customers",
        is_tipped=True,
        typical_tip_percentage=15.0,
        industry="transportation",
    ),
    TTOCCode(
        code="99901",
        title="Non-Tipped Employee",
        description="Employee in a role that does not customarily receive tips",
        is_tipped=False,
        typical_tip_percentage=0.0,
        industry="general",
    ),
]

# Create lookup dictionary
TTOC_LOOKUP: dict[str, TTOCCode] = {code.code: code for code in TTOC_CODES}
