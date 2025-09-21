import pytest
import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path so vm_connection can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vm_connection import SSHConnection

@pytest.fixture
def ssh_connection():
    return SSHConnection(
        host="test.example.com", 
        user="testuser", 
        key_path="/path/to/key", 
        port=22
    )

@pytest.fixture
def mock_stdout():
    def _create_mock(lines, exit_code=0):
        mock = MagicMock()
        mock.channel.exit_status_ready.side_effect = [False] * len(lines) + [True]
        mock.readline.side_effect = lines + ['']
        mock.readlines.return_value = []
        mock.channel.recv_exit_status.return_value = exit_code
        mock.channel.setblocking.return_value = None
        return mock
    return _create_mock
