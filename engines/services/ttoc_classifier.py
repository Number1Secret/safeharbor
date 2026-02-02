"""
TTOC Classifier Service

LLM-based Treasury Tipped Occupation Code classification.
"""

import hashlib
import logging
from datetime import datetime

from engines.schemas.occupation import (
    TTOC_CODES,
    TTOC_LOOKUP,
    TTOCClassificationInput,
    TTOCClassificationOutput,
)
from engines.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v1.0.0"
CONFIDENCE_THRESHOLD = 0.85  # Below this, flag for human review


async def classify_occupation(
    input_data: TTOCClassificationInput,
) -> TTOCClassificationOutput:
    """
    Classify an employee's occupation using LLM.

    Uses Claude to analyze job title, description, and duties
    to determine the most appropriate TTOC code.
    """
    client = get_llm_client()

    # Build context from input
    context_parts = [f"Job Title: {input_data.job_title}"]
    if input_data.job_description:
        context_parts.append(f"Job Description: {input_data.job_description}")
    if input_data.duties:
        context_parts.append(f"Duties: {', '.join(input_data.duties)}")
    if input_data.employer_industry:
        context_parts.append(f"Industry: {input_data.employer_industry}")
    if input_data.tip_frequency:
        context_parts.append(f"Tip Frequency: {input_data.tip_frequency}")
    if input_data.is_customer_facing is not None:
        context_parts.append(f"Customer Facing: {'Yes' if input_data.is_customer_facing else 'No'}")

    context = "\n".join(context_parts)

    # Prepare categories for classification
    categories = [
        {
            "code": code.code,
            "title": code.title,
            "description": code.description,
            "is_tipped": code.is_tipped,
        }
        for code in TTOC_CODES
    ]

    # Call LLM
    result = await client.classify(
        text=input_data.job_title,
        categories=categories,
        context=context,
    )

    response = result["response"]

    # Handle parse errors
    if isinstance(response, dict) and "parse_error" in response:
        logger.error(f"Classification parse error: {response['parse_error']}")
        # Fall back to non-tipped
        return TTOCClassificationOutput(
            employee_id=input_data.employee_id,
            ttoc_code="99901",
            ttoc_title="Non-Tipped Employee",
            ttoc_description="Classification failed - defaulting to non-tipped",
            confidence_score=0.0,
            reasoning=f"Parse error: {response['parse_error']}",
            is_tipped_occupation=False,
            typical_tip_percentage=None,
            alternative_codes=[],
            model_id=result["model_id"],
            prompt_version=PROMPT_VERSION,
            prompt_hash=result["prompt_hash"],
            response_hash=result["response_hash"],
            needs_human_review=True,
            review_reason="Classification failed to parse",
        )

    # Extract classification
    code = response.get("code", "99901")
    confidence = float(response.get("confidence", 0.5))
    reasoning = response.get("reasoning", "No reasoning provided")
    alternatives = response.get("alternatives", [])

    # Look up code details
    ttoc = TTOC_LOOKUP.get(code)
    if not ttoc:
        logger.warning(f"Unknown TTOC code: {code}, defaulting to 99901")
        ttoc = TTOC_LOOKUP["99901"]
        code = "99901"

    # Determine if human review is needed
    needs_review = confidence < CONFIDENCE_THRESHOLD
    review_reason = None
    if needs_review:
        review_reason = f"Confidence {confidence:.2%} below threshold {CONFIDENCE_THRESHOLD:.2%}"

    return TTOCClassificationOutput(
        employee_id=input_data.employee_id,
        ttoc_code=code,
        ttoc_title=ttoc.title,
        ttoc_description=ttoc.description,
        confidence_score=confidence,
        reasoning=reasoning,
        is_tipped_occupation=ttoc.is_tipped,
        typical_tip_percentage=ttoc.typical_tip_percentage,
        alternative_codes=alternatives,
        model_id=result["model_id"],
        prompt_version=PROMPT_VERSION,
        prompt_hash=result["prompt_hash"],
        response_hash=result["response_hash"],
        needs_human_review=needs_review,
        review_reason=review_reason,
    )


def classify_occupation_sync(input_data: TTOCClassificationInput) -> TTOCClassificationOutput:
    """
    Synchronous wrapper for testing without API calls.

    Uses rule-based matching for common job titles.
    """
    title_lower = input_data.job_title.lower()

    # Simple keyword matching for common titles
    keyword_map = {
        "server": "12401",
        "waiter": "12401",
        "waitress": "12401",
        "bartender": "12402",
        "barkeeper": "12402",
        "host": "12403",
        "hostess": "12403",
        "busser": "12404",
        "busboy": "12404",
        "barback": "12405",
        "food runner": "12406",
        "bellhop": "12501",
        "bellman": "12501",
        "concierge": "12502",
        "valet": "12503",
        "room service": "12504",
        "dealer": "12601",
        "croupier": "12601",
        "cocktail server": "12602",
        "cocktail waitress": "12602",
        "hairdresser": "12701",
        "hairstylist": "12701",
        "stylist": "12701",
        "nail tech": "12702",
        "manicurist": "12702",
        "massage": "12703",
        "taxi": "12801",
        "uber": "12801",
        "lyft": "12801",
        "rideshare": "12801",
        "delivery": "12802",
        "doordash": "12802",
        "grubhub": "12802",
    }

    matched_code = "99901"
    confidence = 0.5

    for keyword, code in keyword_map.items():
        if keyword in title_lower:
            matched_code = code
            confidence = 0.95
            break

    ttoc = TTOC_LOOKUP.get(matched_code, TTOC_LOOKUP["99901"])

    # Generate determinism hashes
    prompt_hash = hashlib.sha256(input_data.job_title.encode()).hexdigest()
    response_hash = hashlib.sha256(matched_code.encode()).hexdigest()

    return TTOCClassificationOutput(
        employee_id=input_data.employee_id,
        ttoc_code=matched_code,
        ttoc_title=ttoc.title,
        ttoc_description=ttoc.description,
        confidence_score=confidence,
        reasoning=f"Matched keyword in job title: {input_data.job_title}",
        is_tipped_occupation=ttoc.is_tipped,
        typical_tip_percentage=ttoc.typical_tip_percentage,
        alternative_codes=[],
        model_id="rule-based-v1",
        prompt_version=PROMPT_VERSION,
        prompt_hash=prompt_hash,
        response_hash=response_hash,
        needs_human_review=confidence < CONFIDENCE_THRESHOLD,
        review_reason=None if confidence >= CONFIDENCE_THRESHOLD else "Low confidence match",
    )
