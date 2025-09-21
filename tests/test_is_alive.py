import pytest
from unittest.mock import patch
from vm_connection import SSHConnection

@pytest.fixture
def ssh_connection():
    return SSHConnection(host="test.example.com", user="testuser", key_path="/path/to/key")

@patch("vm_connection.detect_os_activity")
def test_is_alive_returns_false_when_vm_unresponsive(mock_os_detect, ssh_connection):
    def mock_os(host, port, result):
        result['checks_passed'] = 0
        result['checks_failed'] = 3
        result['failed_checks'] = ['All checks failed']
        return {'os_active': False}
    mock_os_detect.side_effect = mock_os
    assert ssh_connection.is_alive() is False

@patch("vm_connection.detect_os_activity")
def test_is_alive_sets_confidence_correctly(mock_os_detect, ssh_connection):
    def side_effect(host, port, result):
        result['checks_passed'] = 2
        result['checks_failed'] = 1
        return {'os_active': True}
    mock_os_detect.side_effect = side_effect
    assert ssh_connection.is_alive() is True

@patch("vm_connection.detect_os_activity")
@patch("vm_connection.check_ssh_connectivity")
def test_is_alive_returns_true_when_vm_responsive(mock_ssh_check, mock_os_detect, ssh_connection):
    """Test that is_alive returns True when VM is responsive"""
    def mock_os_detect_side_effect(host, port, result):
        result['checks_passed'] = 3
        result['checks_failed'] = 0
        return {'os_active': True}
    
    def mock_ssh_check_side_effect(conn, result):
        result['checks_passed'] += 1
        return True
    
    mock_os_detect.side_effect = mock_os_detect_side_effect
    mock_ssh_check.side_effect = mock_ssh_check_side_effect
    result = ssh_connection.is_alive()
    assert result is True
    mock_os_detect.assert_called_once()
