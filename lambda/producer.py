"""
Lambda Producer Function - Code Execution Job Submission
Validates requests and enqueues jobs to SQS

Author: [Your Name]
Purpose: API Gateway handler for code execution engine
"""

import json
import uuid
import os
import re
from datetime import datetime
from typing import Dict, Tuple

import boto3
from botocore.exceptions import ClientError

# Configuration
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'code-executions')
MAX_CODE_SIZE = 10 * 1024  # 10 KB
MAX_TIMEOUT = 10  # seconds
ALLOWED_LANGUAGES = ['python', 'javascript', 'ruby', 'go']

# AWS Clients
sqs = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)

# ============================================================================
# INPUT VALIDATION
# ============================================================================

def validate_request(body: Dict) -> Tuple[bool, str]:
    """
    Validate incoming request payload.
    
    Security checks:
    - Required fields present
    - Language whitelist
    - Code size limits
    - Timeout bounds
    - Basic injection attempt detection
    """
    # Check required fields
    if 'language' not in body:
        return False, "Missing required field: 'language'"
    if 'code' not in body:
        return False, "Missing required field: 'code'"
    
    # Language whitelist
    language = body['language'].lower()
    if language not in ALLOWED_LANGUAGES:
        return False, f"Unsupported language '{language}'. Allowed: {ALLOWED_LANGUAGES}"
    
    # Code validation
    code = body['code']
    if not isinstance(code, str):
        return False, "Field 'code' must be a string"
    
    if len(code) == 0:
        return False, "Code cannot be empty"
    
    if len(code) > MAX_CODE_SIZE:
        return False, f"Code exceeds maximum size of {MAX_CODE_SIZE} bytes"
    
    # Timeout validation
    timeout = body.get('timeout', 5)
    if not isinstance(timeout, (int, float)):
        return False, "Field 'timeout' must be a number"
    
    if timeout <= 0 or timeout > MAX_TIMEOUT:
        return False, f"Timeout must be between 1 and {MAX_TIMEOUT} seconds"
    
    # Basic injection detection (flag suspicious patterns)
    suspicious_patterns = [
        r'rm\s+-rf',           # Destructive commands
        r'wget|curl',          # Network access attempts
        r'eval\s*\(',          # Eval injection
        r'/etc/passwd',        # System file access
        r'>&\s*/dev/tcp',      # Reverse shell attempts
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            # Don't block, but log for monitoring
            print(f"WARNING: Suspicious pattern detected: {pattern}")
    
    return True, ""

# ============================================================================
# JOB CREATION
# ============================================================================

def create_job(body: Dict) -> Dict:
    """
    Create a job payload with unique ID and metadata.
    """
    job_id = str(uuid.uuid4())
    
    job = {
        'job_id': job_id,
        'language': body['language'].lower(),
        'code': body['code'],
        'timeout': body.get('timeout', 5),
        'submitted_at': datetime.utcnow().isoformat(),
        'metadata': {
            'source_ip': 'api-gateway',  # Can be enhanced with actual IP
            'user_agent': body.get('user_agent', 'unknown')
        }
    }
    
    return job

# ============================================================================
# SQS OPERATIONS
# ============================================================================

def enqueue_job(job: Dict) -> Tuple[bool, str]:
    """
    Send job to SQS queue with deduplication.
    
    Returns: (success, message_id_or_error)
    """
    try:
        response = sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(job),
            MessageAttributes={
                'job_id': {
                    'StringValue': job['job_id'],
                    'DataType': 'String'
                },
                'language': {
                    'StringValue': job['language'],
                    'DataType': 'String'
                }
            }
        )
        
        return True, response['MessageId']
    
    except ClientError as e:
        print(f"ERROR: Failed to enqueue job: {str(e)}")
        return False, str(e)

# ============================================================================
# DYNAMODB OPERATIONS
# ============================================================================

def initialize_job_record(job_id: str, language: str):
    """
    Create initial PENDING record in DynamoDB.
    This allows clients to poll for status immediately.
    """
    try:
        table.put_item(
            Item={
                'job_id': job_id,
                'status': 'PENDING',
                'language': language,
                'submitted_at': datetime.utcnow().isoformat(),
                'output': '',
                'error': '',
                'execution_time_ms': 0
            }
        )
        return True
    except ClientError as e:
        print(f"ERROR: Failed to create DynamoDB record: {str(e)}")
        return False

# ============================================================================
# LAMBDA HANDLER
# ============================================================================

def lambda_handler(event, context):
    """
    Main Lambda handler for API Gateway requests.
    
    Endpoint: POST /execute
    Request Body: {
        "language": "python",
        "code": "print('hello')",
        "timeout": 5  // optional
    }
    
    Response: {
        "job_id": "uuid",
        "status": "PENDING",
        "status_url": "/status/{job_id}"
    }
    """
    print(f"Received event: {json.dumps(event)}")
    
    # Parse request body
    try:
        if 'body' in event:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        else:
            body = event
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Invalid JSON in request body'
            })
        }
    
    # Validate request
    is_valid, error_msg = validate_request(body)
    if not is_valid:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': error_msg
            })
        }
    
    # Create job
    job = create_job(body)
    job_id = job['job_id']
    
    # Initialize DynamoDB record (PENDING status)
    if not initialize_job_record(job_id, job['language']):
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to initialize job record'
            })
        }
    
    # Enqueue to SQS
    success, message_id_or_error = enqueue_job(job)
    if not success:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Failed to enqueue job: {message_id_or_error}'
            })
        }
    
    # Success response
    return {
        'statusCode': 202,  # Accepted (async processing)
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'job_id': job_id,
            'status': 'PENDING',
            'message': 'Job queued for execution',
            'status_url': f'/status/{job_id}',
            'estimated_wait_seconds': 5
        })
    }
