"""
Occupation AI MCP Tool

TTOC classification exposed as an MCP tool.
"""

from engines.schemas.occupation import TTOC_CODES, TTOCClassificationInput
from engines.services.ttoc_classifier import classify_occupation, classify_occupation_sync
from engines.tools.premium_engine import mcp


@mcp.tool()
async def classify_employee_occupation(
    employee_id: str,
    job_title: str,
    job_description: str | None = None,
    duties: list[str] | None = None,
    employer_industry: str | None = None,
    tip_frequency: str | None = None,
    is_customer_facing: bool | None = None,
    use_llm: bool = True,
) -> dict:
    """
    Classify an employee's occupation using Treasury Tipped Occupation Codes (TTOC).

    Uses AI to analyze job title, description, and duties to determine
    the most appropriate TTOC code from the 70+ IRS-defined codes.

    Args:
        employee_id: Unique employee identifier
        job_title: Employee's job title
        job_description: Detailed job description
        duties: List of specific job duties
        employer_industry: Industry (restaurant, hospitality, casino, etc.)
        tip_frequency: How often tips are received (always/frequently/occasionally/rarely/never)
        is_customer_facing: Whether role involves direct customer interaction
        use_llm: Use LLM for classification (False uses rule-based fallback)

    Returns:
        Classification result with TTOC code, confidence, and reasoning

    Example:
        Job Title: "Server"
        Result: TTOC 12401 (Waiter/Waitress), confidence 0.95, is_tipped=True
    """
    input_data = TTOCClassificationInput(
        employee_id=employee_id,
        job_title=job_title,
        job_description=job_description,
        duties=duties or [],
        employer_industry=employer_industry,
        tip_frequency=tip_frequency,
        is_customer_facing=is_customer_facing,
    )

    if use_llm:
        result = await classify_occupation(input_data)
    else:
        result = classify_occupation_sync(input_data)

    return {
        "employee_id": result.employee_id,
        "ttoc_code": result.ttoc_code,
        "ttoc_title": result.ttoc_title,
        "ttoc_description": result.ttoc_description,
        "confidence_score": result.confidence_score,
        "reasoning": result.reasoning,
        "is_tipped_occupation": result.is_tipped_occupation,
        "typical_tip_percentage": result.typical_tip_percentage,
        "alternative_codes": result.alternative_codes,
        "model_id": result.model_id,
        "prompt_version": result.prompt_version,
        "prompt_hash": result.prompt_hash,
        "response_hash": result.response_hash,
        "needs_human_review": result.needs_human_review,
        "review_reason": result.review_reason,
    }


@mcp.tool()
async def list_ttoc_codes(
    industry: str | None = None,
    tipped_only: bool = False,
) -> list[dict]:
    """
    List available Treasury Tipped Occupation Codes.

    Args:
        industry: Filter by industry (restaurant, hospitality, casino, etc.)
        tipped_only: Only return codes for tipped occupations

    Returns:
        List of TTOC codes with descriptions
    """
    codes = TTOC_CODES

    if industry:
        codes = [c for c in codes if c.industry.lower() == industry.lower()]

    if tipped_only:
        codes = [c for c in codes if c.is_tipped]

    return [
        {
            "code": c.code,
            "title": c.title,
            "description": c.description,
            "is_tipped": c.is_tipped,
            "typical_tip_percentage": c.typical_tip_percentage,
            "industry": c.industry,
        }
        for c in codes
    ]


@mcp.tool()
async def get_ttoc_code_details(code: str) -> dict | None:
    """
    Get details for a specific TTOC code.

    Args:
        code: The TTOC code (e.g., "12401")

    Returns:
        Code details or None if not found
    """
    from engines.schemas.occupation import TTOC_LOOKUP

    ttoc = TTOC_LOOKUP.get(code)
    if not ttoc:
        return None

    return {
        "code": ttoc.code,
        "title": ttoc.title,
        "description": ttoc.description,
        "is_tipped": ttoc.is_tipped,
        "typical_tip_percentage": ttoc.typical_tip_percentage,
        "industry": ttoc.industry,
    }
