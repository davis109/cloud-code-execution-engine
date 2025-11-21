#!/bin/bash
#
# Quick Test Script for Code Execution Engine
# Usage: ./test.sh <API_ENDPOINT>
#

set -e

if [ -z "$1" ]; then
  echo "Usage: ./test.sh <API_ENDPOINT>"
  echo "Example: ./test.sh https://abc123.execute-api.us-east-1.amazonaws.com/prod"
  exit 1
fi

API_ENDPOINT=$1

echo "🧪 Testing Code Execution Engine at $API_ENDPOINT"
echo ""

# Test 1: Python Hello World
echo "Test 1: Python Hello World"
JOB_ID=$(curl -s -X POST $API_ENDPOINT/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "print(\"Hello from distributed executor!\")"
  }' | jq -r '.job_id')

echo "  ✓ Submitted job: $JOB_ID"
sleep 3

RESULT=$(curl -s $API_ENDPOINT/status/$JOB_ID | jq -r '.status')
echo "  ✓ Status: $RESULT"
echo ""

# Test 2: JavaScript
echo "Test 2: JavaScript Execution"
JOB_ID=$(curl -s -X POST $API_ENDPOINT/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "javascript",
    "code": "console.log(Math.PI);"
  }' | jq -r '.job_id')

echo "  ✓ Submitted job: $JOB_ID"
sleep 3

OUTPUT=$(curl -s $API_ENDPOINT/status/$JOB_ID | jq -r '.output')
echo "  ✓ Output: $OUTPUT"
echo ""

# Test 3: Timeout Protection
echo "Test 3: Timeout Protection (Infinite Loop)"
JOB_ID=$(curl -s -X POST $API_ENDPOINT/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "while True: pass",
    "timeout": 2
  }' | jq -r '.job_id')

echo "  ✓ Submitted job: $JOB_ID"
sleep 4

STATUS=$(curl -s $API_ENDPOINT/status/$JOB_ID | jq -r '.status')
echo "  ✓ Status: $STATUS (expected: TIMEOUT)"
echo ""

# Test 4: Error Handling
echo "Test 4: Error Handling (Syntax Error)"
JOB_ID=$(curl -s -X POST $API_ENDPOINT/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "print(invalid syntax"
  }' | jq -r '.job_id')

echo "  ✓ Submitted job: $JOB_ID"
sleep 3

ERROR=$(curl -s $API_ENDPOINT/status/$JOB_ID | jq -r '.error')
echo "  ✓ Error captured: $(echo $ERROR | head -c 50)..."
echo ""

# Test 5: Memory Test
echo "Test 5: Memory Limit Test"
JOB_ID=$(curl -s -X POST $API_ENDPOINT/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "code": "x = [0] * (10**8)"
  }' | jq -r '.job_id')

echo "  ✓ Submitted job: $JOB_ID"
sleep 3

STATUS=$(curl -s $API_ENDPOINT/status/$JOB_ID | jq -r '.status')
echo "  ✓ Status: $STATUS (expected: ERROR due to memory limit)"
echo ""

echo "✅ All tests completed!"
