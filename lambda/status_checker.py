"""
Lambda Status Checker - Retrieve Job Results
Queries DynamoDB for job status and results

Author: [Your Name]
"""

import json
import os
from decimal import Decimal
from typing import Dict

import boto3
from botocore.exceptions import ClientError

# Configuration
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'code-executions')

# AWS Clients
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)

# Helper class to convert Decimal to int/float for JSON serialization
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    Lambda handler for status check requests.
    
    Endpoint: GET /status/{job_id}
    
    Response: {
        "job_id": "uuid",
        "status": "SUCCESS" | "ERROR" | "TIMEOUT" | "PENDING",
        "output": "stdout content",
        "error": "stderr content",
        "execution_time_ms": 487
    }
    """
    print(f"Received event: {json.dumps(event)}")
    
    # Extract job_id from path parameters
    try:
        job_id = event['pathParameters']['job_id']
    except (KeyError, TypeError):
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Missing job_id in path'
            })
        }
    
    # Query DynamoDB
    try:
        response = table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f'Job {job_id} not found'
                })
            }
        
        item = response['Item']
        
        # Build response
        result = {
            'job_id': item['job_id'],
            'status': item['status'],
            'language': item.get('language', 'unknown'),
            'submitted_at': item.get('submitted_at', ''),
            'execution_time_ms': item.get('execution_time_ms', 0)
        }
        
        # Include output/error only if execution completed
        if item['status'] != 'PENDING':
            result['output'] = item.get('output', '')
            result['error'] = item.get('error', '')
            result['exit_code'] = item.get('exit_code', 0)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-cache'  # Prevent caching of status
            },
            'body': json.dumps(result, cls=DecimalEncoder)
        }
    
    except ClientError as e:
        print(f"ERROR: DynamoDB query failed: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to retrieve job status'
            })
        }
