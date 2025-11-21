"""
Unit tests for the code executor worker
Run with: pytest test_executor.py
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock boto3 before importing executor
sys.modules['boto3'] = MagicMock()

from worker.executor import validate_job, execute_code

class TestJobValidation:
    """Test job validation logic"""
    
    def test_valid_job(self):
        job = {
            'job_id': 'test-123',
            'language': 'python',
            'code': 'print("hello")',
            'timeout': 5
        }
        is_valid, error = validate_job(job)
        assert is_valid is True
        assert error is None
    
    def test_missing_job_id(self):
        job = {
            'language': 'python',
            'code': 'print("hello")'
        }
        is_valid, error = validate_job(job)
        assert is_valid is False
        assert 'job_id' in error
    
    def test_unsupported_language(self):
        job = {
            'job_id': 'test-123',
            'language': 'haskell',
            'code': 'main = putStrLn "hello"'
        }
        is_valid, error = validate_job(job)
        assert is_valid is False
        assert 'Unsupported language' in error
    
    def test_code_too_large(self):
        job = {
            'job_id': 'test-123',
            'language': 'python',
            'code': 'x = 1\n' * 10000  # > 10KB
        }
        is_valid, error = validate_job(job)
        assert is_valid is False
        assert 'exceeds size limit' in error
    
    def test_invalid_timeout(self):
        job = {
            'job_id': 'test-123',
            'language': 'python',
            'code': 'print("hello")',
            'timeout': 100  # Exceeds MAX_EXECUTION_TIME
        }
        is_valid, error = validate_job(job)
        assert is_valid is False
        assert 'Invalid timeout' in error


class TestCodeExecution:
    """Test code execution (requires Docker)"""
    
    @pytest.mark.skipif(not os.system('docker --version') == 0, 
                        reason="Docker not available")
    def test_python_hello_world(self):
        result = execute_code('python', 'print("hello world")', timeout=5)
        assert result['status'] == 'SUCCESS'
        assert 'hello world' in result['output']
        assert result['execution_time_ms'] > 0
    
    @pytest.mark.skipif(not os.system('docker --version') == 0,
                        reason="Docker not available")
    def test_python_syntax_error(self):
        result = execute_code('python', 'print(invalid syntax', timeout=5)
        assert result['status'] == 'ERROR'
        assert len(result['error']) > 0
    
    @pytest.mark.skipif(not os.system('docker --version') == 0,
                        reason="Docker not available")
    def test_timeout_enforcement(self):
        result = execute_code('python', 'while True: pass', timeout=2)
        assert result['status'] == 'TIMEOUT'
        assert 'exceeded time limit' in result['error']
    
    @pytest.mark.skipif(not os.system('docker --version') == 0,
                        reason="Docker not available")
    def test_javascript_execution(self):
        result = execute_code('javascript', 'console.log(Math.PI);', timeout=5)
        assert result['status'] == 'SUCCESS'
        assert '3.14' in result['output']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
