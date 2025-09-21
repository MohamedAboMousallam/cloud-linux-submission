import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vm_connection import SSHConnection
import pytest

def test_ssh_connection_initialization_with_valid_parameters():
    conn = SSHConnection("example.com", "testuser", "/path/to/key", 2222)
    assert conn.host == "example.com"
    assert conn.user == "testuser"
    assert conn.key_path == "/path/to/key"
    assert conn.port == 2222

def test_ssh_connection_connect_validates_key_path(ssh_connection):
    ssh_connection.key_path = None
    with pytest.raises(ValueError, match="Key_path is required"):
        ssh_connection.connect()
