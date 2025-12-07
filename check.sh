#!/bin/bash
# Script to format code and run tests for the Leave Me Alone app

cd "$(dirname "$0")"

# Activate virtual environment if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    source .venv/bin/activate
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  FORMATTING CODE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if black is installed
if ! command -v black &> /dev/null; then
    echo "⚠️  Black is not installed."
    echo "Installing black..."
    pip install black
    echo ""
fi

# Run black formatter
echo "Formatting code with black..."
black app

FORMAT_EXIT=$?

if [ $FORMAT_EXIT -eq 0 ]; then
    echo "✅ Code formatting completed!"
else
    echo "❌ Code formatting encountered issues."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  RUNNING TESTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run pytest with quiet mode using python -m to ensure proper path
python -m pytest -q

TEST_EXIT=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $FORMAT_EXIT -eq 0 ]; then
    echo "✅ Formatting: PASSED"
else
    echo "❌ Formatting: FAILED"
fi

if [ $TEST_EXIT -eq 0 ]; then
    echo "✅ Tests: PASSED (All tests passed)"
else
    echo "❌ Tests: FAILED (Some tests failed)"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Exit with failure if either formatting or tests failed
if [ $FORMAT_EXIT -ne 0 ] || [ $TEST_EXIT -ne 0 ]; then
    exit 1
fi

exit 0
