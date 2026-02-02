"""
SafeHarbor AI Calculation Engines - MCP Server

FastMCP server exposing tax calculation tools:
- Premium Engine: FLSA Section 7 Regular Rate calculation
- Phase-Out Filter: MAGI-based phase-out calculation
- Occupation AI: TTOC classification (future)
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the MCP instance and tools from tool modules
# This registers all the tools with the MCP server
from engines.tools.premium_engine import mcp  # noqa: F401
from engines.tools.phase_out_filter import *  # noqa: F401, F403


@asynccontextmanager
async def lifespan(server: FastMCP):
    """MCP server lifespan manager."""
    logger.info("SafeHarbor Calculation Engines starting...")
    yield
    logger.info("SafeHarbor Calculation Engines shutting down...")


# Configure the MCP server
mcp.name = "SafeHarbor Calculation Engines"
mcp.description = """
SafeHarbor AI Tax Calculation Engines for OBBB Compliance.

Provides three core calculation capabilities:

1. **Premium Engine** (calculate_flsa_regular_rate, calculate_qualified_tips)
   - Implements FLSA Section 7 Regular Rate of Pay
   - Calculates qualified overtime premium for OBBB exemption
   - Handles tip credit calculations with TTOC eligibility

2. **Phase-Out Filter** (calculate_magi_phase_out, estimate_employee_magi, check_employee_phase_out_risk)
   - Tracks Modified Adjusted Gross Income
   - Applies OBBB phase-out rules based on filing status
   - Provides early warning for phase-out risk

3. **Occupation AI** (coming soon)
   - LLM-based Treasury Tipped Occupation Code classification
   - Semantic matching of job titles to TTOC codes
   - Confidence scoring for human review

All calculations maintain full audit trails with reproducibility guarantees.
"""


def main():
    """Run the MCP server."""
    logger.info("Starting SafeHarbor Calculation Engines MCP Server")
    mcp.run()


if __name__ == "__main__":
    main()
