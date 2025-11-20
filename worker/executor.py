#!/usr/bin/env python3
"""
Distributed Code Execution Worker - Production Grade
Polls SQS, executes code in Docker containers, writes results to DynamoDB.

Author: [Your Name]
Purpose: Resume project - Distributed code execution engine
"""

import json
import time
import logging
import signal
import sys
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import subprocess
import os
import hashlib

import boto3
from botocore.exceptions import ClientError

# ============================================================================
# CONFIGURATION
# ============================================================================

# AWS Resources (set via environment variables or defaults)
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'code-executions')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Execution Limits
MAX_EXECUTION_TIME = 10  # seconds
MAX_MEMORY_MB = 256
MAX_CPU_CORES = 0.5
MAX_PIDS = 50
MAX_CODE_SIZE = 10 * 1024  # 10 KB

# Worker Configuration
POLL_INTERVAL = 20  # SQS long polling duration
VISIBILITY_TIMEOUT = 30  # SQS message visibility
MAX_MESSAGES = 1  # Process one job at a time for t2.micro
WORKER_ID = os.environ.get('HOSTNAME', 'worker-001')

# Docker Image Mapping (use Alpine for minimal size)
LANGUAGE_IMAGES = {
    'python': 'python:3.11-alpine',
    'javascript': 'node:20-alpine',
    'ruby': 'ruby:3.2-alpine',
    'go': 'golang:1.21-alpine',
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/code-executor.log')
    ]
)
logger = logging.getLogger('CodeExecutor')

# ============================================================================
# AWS CLIENT INITIALIZATION
# ============================================================================

# Use IAM role credentials (no hardcoded keys!)
sqs = boto3.client('sqs', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)

# ============================================================================
# GRACEFUL SHUTDOWN HANDLER
# ============================================================================

shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_event.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ============================================================================
# DOCKER IMAGE PRE-PULLING
# ============================================================================

def prepull_images():
    """
    Pre-pull all supported Docker images to eliminate cold start delays.
    This is a CRITICAL optimization for user experience.
    """
    logger.info("Pre-pulling Docker images...")
    for language, image in LANGUAGE_IMAGES.items():
        try:
            logger.info(f"Pulling {image}...")
            result = subprocess.run(
                ['docker', 'pull', image],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                logger.info(f"✓ Successfully pulled {image}")
            else:
                logger.error(f"✗ Failed to pull {image}: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error(f"✗ Timeout pulling {image}")
        except Exception as e:
            logger.error(f"✗ Error pulling {image}: {str(e)}")

# ============================================================================
# INPUT VALIDATION & SANITIZATION
# ============================================================================

def validate_job(job: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate job payload to prevent injection attacks and resource abuse.
    
    Returns: (is_valid, error_message)
    """
    # Required fields
    required = ['job_id', 'language', 'code']
    for field in required:
        if field not in job:
            return False, f"Missing required field: {field}"
    
    # Language whitelist
    if job['language'] not in LANGUAGE_IMAGES:
        return False, f"Unsupported language: {job['language']}. Supported: {list(LANGUAGE_IMAGES.keys())}"
    
    # Code size limit
    if len(job['code']) > MAX_CODE_SIZE:
        return False, f"Code exceeds size limit of {MAX_CODE_SIZE} bytes"
    
    # Timeout validation
    timeout = job.get('timeout', MAX_EXECUTION_TIME)
    if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > MAX_EXECUTION_TIME:
        return False, f"Invalid timeout. Must be 1-{MAX_EXECUTION_TIME} seconds"
    
    return True, None

# ============================================================================
# SECURE CODE EXECUTION
# ============================================================================

def execute_code(language: str, code: str, timeout: int = MAX_EXECUTION_TIME) -> Dict:
    """
    Execute code in an isolated Docker container with strict security controls.
    
    Security Measures:
    - Network isolation (--network none)
    - Memory limit (--memory)
    - CPU limit (--cpus)
    - Process limit (--pids-limit)
    - Read-only filesystem (--read-only)
    - Drop all capabilities (--cap-drop=ALL)
    - Prevent privilege escalation (--security-opt=no-new-privileges)
    
    Returns: {
        'status': 'SUCCESS' | 'ERROR' | 'TIMEOUT',
        'output': stdout,
        'error': stderr,
        'execution_time_ms': int
    }
    """
    start_time = time.time()
    image = LANGUAGE_IMAGES[language]
    
    # Build execution command based on language
    exec_commands = {
        'python': ['python', '-c', code],
        'javascript': ['node', '-e', code],
        'ruby': ['ruby', '-e', code],
        'go': ['go', 'run', '/dev/stdin'],  # Go reads from stdin
    }
    
    # Construct Docker command with MAXIMUM security
    docker_cmd = [
        'docker', 'run',
        '--rm',                              # Auto-remove container
        '--interactive',                     # For stdin input
        '--network', 'none',                 # NO network access
        '--cpus', str(MAX_CPU_CORES),       # CPU limit
        '--memory', f'{MAX_MEMORY_MB}m',    # Memory limit
        '--pids-limit', str(MAX_PIDS),      # Prevent fork bombs
        '--read-only',                       # Read-only filesystem
        '--cap-drop', 'ALL',                 # Drop all Linux capabilities
        '--security-opt', 'no-new-privileges',  # Prevent privilege escalation
        image
    ] + exec_commands[language][:-1]  # Add command without code
    
    logger.info(f"Executing {language} code in container (timeout={timeout}s)")
    
    try:
        # For Go, we need to pass code via stdin
        stdin_input = code if language == 'go' else None
        
        # Execute with timeout enforcement
        result = subprocess.run(
            docker_cmd + [exec_commands[language][-1]],
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_input
        )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return {
            'status': 'SUCCESS' if result.returncode == 0 else 'ERROR',
            'output': result.stdout[:4000],  # Truncate to fit DynamoDB item size
            'error': result.stderr[:4000],
            'execution_time_ms': execution_time_ms,
            'exit_code': result.returncode
        }
    
    except subprocess.TimeoutExpired:
        logger.warning(f"Execution timeout after {timeout}s")
        # Kill the container (Docker --rm will clean up)
        return {
            'status': 'TIMEOUT',
            'output': '',
            'error': f'Execution exceeded time limit of {timeout}s',
            'execution_time_ms': timeout * 1000,
            'exit_code': -1
        }
    
    except Exception as e:
        logger.error(f"Execution error: {str(e)}", exc_info=True)
        return {
            'status': 'ERROR',
            'output': '',
            'error': f'Internal execution error: {str(e)}',
            'execution_time_ms': int((time.time() - start_time) * 1000),
            'exit_code': -1
        }

# ============================================================================
# DYNAMODB OPERATIONS
# ============================================================================

def write_result(job_id: str, result: Dict, job_metadata: Dict):
    """
    Write execution result to DynamoDB with TTL for auto-cleanup.
    
    Implements exponential backoff for transient failures.
    """
    item = {
        'job_id': job_id,
        'status': result['status'],
        'output': result.get('output', ''),
        'error': result.get('error', ''),
        'execution_time_ms': result['execution_time_ms'],
        'exit_code': result.get('exit_code', -1),
        'language': job_metadata.get('language', 'unknown'),
        'worker_id': WORKER_ID,
        'timestamp': datetime.utcnow().isoformat(),
        'ttl': int((datetime.utcnow() + timedelta(days=7)).timestamp())  # Auto-delete after 7 days
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            table.put_item(Item=item)
            logger.info(f"✓ Wrote result for job {job_id} to DynamoDB")
            return True
        except ClientError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"DynamoDB write failed (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"✗ Failed to write result for job {job_id}: {str(e)}")
                return False
    
    return False

# ============================================================================
# SQS MESSAGE PROCESSING
# ============================================================================

def process_message(message):
    """
    Process a single SQS message containing a code execution job.
    
    Flow:
    1. Parse and validate message
    2. Execute code in Docker
    3. Write result to DynamoDB
    4. Delete message from SQS
    """
    receipt_handle = message['ReceiptHandle']
    
    try:
        # Parse job payload
        job = json.loads(message['Body'])
        job_id = job.get('job_id', 'unknown')
        
        logger.info(f"Processing job {job_id}")
        
        # Validate job
        is_valid, error_msg = validate_job(job)
        if not is_valid:
            logger.error(f"Invalid job {job_id}: {error_msg}")
            result = {
                'status': 'ERROR',
                'output': '',
                'error': f'Validation error: {error_msg}',
                'execution_time_ms': 0,
                'exit_code': -1
            }
            write_result(job_id, result, job)
            delete_message(receipt_handle)
            return
        
        # Execute code
        result = execute_code(
            language=job['language'],
            code=job['code'],
            timeout=job.get('timeout', MAX_EXECUTION_TIME)
        )
        
        # Write result to DynamoDB
        write_result(job_id, result, job)
        
        # Delete message from queue (only after successful processing)
        delete_message(receipt_handle)
        
        logger.info(f"✓ Completed job {job_id} with status {result['status']}")
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in message: {str(e)}")
        delete_message(receipt_handle)  # Remove malformed messages
    
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        # Don't delete message - let it return to queue for retry

def delete_message(receipt_handle: str):
    """Delete message from SQS queue."""
    try:
        sqs.delete_message(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle
        )
        logger.debug("✓ Deleted message from queue")
    except ClientError as e:
        logger.error(f"✗ Failed to delete message: {str(e)}")

# ============================================================================
# MAIN POLLING LOOP
# ============================================================================

def poll_queue():
    """
    Main worker loop: Long-poll SQS and process messages.
    
    Uses long polling (WaitTimeSeconds=20) to reduce empty responses
    and minimize costs (fewer API calls).
    """
    logger.info(f"Worker {WORKER_ID} started. Polling queue: {SQS_QUEUE_URL}")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while not shutdown_event.is_set():
        try:
            # Long poll for messages (reduces costs and latency)
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=MAX_MESSAGES,
                WaitTimeSeconds=POLL_INTERVAL,
                VisibilityTimeout=VISIBILITY_TIMEOUT,
                AttributeNames=['ApproximateReceiveCount']
            )
            
            messages = response.get('Messages', [])
            
            if messages:
                logger.info(f"Received {len(messages)} message(s)")
                for message in messages:
                    if shutdown_event.is_set():
                        logger.info("Shutdown requested. Stopping message processing.")
                        break
                    process_message(message)
                
                consecutive_errors = 0  # Reset error counter on success
            else:
                logger.debug("No messages available")
        
        except ClientError as e:
            consecutive_errors += 1
            logger.error(f"SQS error ({consecutive_errors}/{max_consecutive_errors}): {str(e)}")
            
            if consecutive_errors >= max_consecutive_errors:
                logger.critical("Too many consecutive errors. Shutting down worker.")
                break
            
            time.sleep(5)  # Back off on errors
        
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            
            if consecutive_errors >= max_consecutive_errors:
                logger.critical("Too many consecutive errors. Shutting down worker.")
                break
            
            time.sleep(5)
    
    logger.info("Worker shutting down gracefully.")

# ============================================================================
# HEALTH CHECK ENDPOINT (Optional - for monitoring)
# ============================================================================

def health_check():
    """
    Simple health check that can be queried by CloudWatch or external monitors.
    Writes a heartbeat to a local file that can be checked.
    """
    while not shutdown_event.is_set():
        try:
            with open('/tmp/worker-heartbeat', 'w') as f:
                f.write(f"{datetime.utcnow().isoformat()}\n")
            time.sleep(30)
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """
    Worker startup sequence:
    1. Validate configuration
    2. Pre-pull Docker images
    3. Start health check thread
    4. Begin polling SQS
    """
    logger.info("=" * 80)
    logger.info("Code Execution Worker Starting")
    logger.info(f"Worker ID: {WORKER_ID}")
    logger.info(f"Region: {AWS_REGION}")
    logger.info(f"Queue: {SQS_QUEUE_URL}")
    logger.info(f"Table: {DYNAMODB_TABLE}")
    logger.info("=" * 80)
    
    # Validate configuration
    if not SQS_QUEUE_URL:
        logger.error("SQS_QUEUE_URL environment variable not set!")
        sys.exit(1)
    
    # Pre-pull Docker images (critical for performance)
    prepull_images()
    
    # Start health check thread
    health_thread = threading.Thread(target=health_check, daemon=True)
    health_thread.start()
    
    # Start main polling loop
    try:
        poll_queue()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Worker stopped")

if __name__ == '__main__':
    main()
