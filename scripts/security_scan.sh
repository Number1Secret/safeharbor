#!/usr/bin/env bash
#
# SafeHarbor AI — Security Scan Script
#
# Runs static analysis and dependency vulnerability checks.
# Used for SOC 2 evidence collection.
#

set -euo pipefail

echo "========================================="
echo " SafeHarbor AI Security Scan"
echo "========================================="
echo ""

FAILURES=0

# 1. Bandit — Python security linter
echo "--- [1/3] Bandit: Static security analysis ---"
if bandit -r backend engines compliance_vault workers -ll --exclude tests -f json -o bandit-report.json 2>/dev/null; then
    echo "PASS: No high/medium severity issues found."
else
    echo "WARN: Bandit found issues. See bandit-report.json"
    FAILURES=$((FAILURES + 1))
fi
echo ""

# 2. pip-audit — Dependency vulnerability check
echo "--- [2/3] pip-audit: Dependency vulnerability check ---"
if pip-audit --format=json --output=pip-audit-report.json 2>/dev/null; then
    echo "PASS: No known vulnerabilities in dependencies."
else
    echo "WARN: Vulnerabilities found. See pip-audit-report.json"
    FAILURES=$((FAILURES + 1))
fi
echo ""

# 3. Secrets detection — Check for hardcoded secrets
echo "--- [3/3] Secrets detection: Checking for hardcoded secrets ---"
SECRETS_FOUND=0
# Check for common secret patterns (API keys, passwords, tokens)
if grep -rn --include="*.py" -E "(password|secret|api_key|token)\s*=\s*\"[^\"]{8,}\"" backend engines compliance_vault workers 2>/dev/null | grep -v "test" | grep -v "CHANGE-ME" | grep -v "example" | grep -v "#" | head -20; then
    echo "WARN: Potential hardcoded secrets found above."
    SECRETS_FOUND=1
    FAILURES=$((FAILURES + 1))
else
    echo "PASS: No obvious hardcoded secrets detected."
fi
echo ""

# Summary
echo "========================================="
if [ $FAILURES -eq 0 ]; then
    echo " ALL CHECKS PASSED"
else
    echo " $FAILURES check(s) had warnings"
fi
echo "========================================="

exit $FAILURES
