import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vm_connection import CommandTimeoutError

@patch("paramiko.SSHClient")
def test_execute_command_returns_correct_exit_code(mock_sshclient, ssh_connection):
    mock_client = MagicMock()
    mock_sshclient.return_value = mock_client
    stdout = MagicMock()
    stdout.channel.exit_status_ready.return_value = True
    stdout.channel.recv_exit_status.return_value = 0
    stdout.readlines.return_value = []
    stderr = MagicMock()
    stderr.readlines.return_value = []
    mock_client.exec_command.return_value = (None, stdout, stderr)

    ssh_connection.connect()
    exit_code = ssh_connection.execute("echo test")

    assert exit_code == 0
    mock_client.exec_command.assert_called_once_with("echo test")

@patch("select.select")
@patch("paramiko.SSHClient")
def test_execute_command_with_timeout_raises_timeout_error(mock_sshclient, mock_select, ssh_connection):
    mock_client = MagicMock()
    mock_sshclient.return_value = mock_client
    stdout = MagicMock()
    stdout.channel.exit_status_ready.return_value = False
    stderr = MagicMock()
    mock_client.exec_command.return_value = (None, stdout, stderr)
    mock_select.return_value = ([], [], [])
    ssh_connection.connect()
    with pytest.raises(CommandTimeoutError):
        ssh_connection.execute("long_running_command", timeout=1)

@patch("select.select")
@patch("paramiko.SSHClient")
def test_execute_command_handles_non_zero_exit_code(self, mock_sshclient, mock_select, SSHConnection, mock_stdout):
    """Test that execute method properly handles commands with non-zero exit codes"""
    # Arrange
    mock_client_instance = MagicMock()
    mock_sshclient.return_value = mock_client_instance
    
    stdout_mock = mock_stdout(["error output\n"], exit_code=1)
    stderr_mock = mock_stdout(["stderr message\n"])
    
    mock_client_instance.exec_command.return_value = (None, stdout_mock, stderr_mock)
    mock_select.side_effect = [([stdout_mock.channel], [], []), ([], [], [])]
    
    SSHConnection.connect()
    
    # Act
    exit_code = SSHConnection.execute("failing_command")
    
    # Assert
    assert exit_code == 1

@patch("select.select")
@patch("paramiko.SSHClient")
def test_execute_command_with_timeout_raises_timeout_error(self, mock_sshclient, mock_select, SSHConnection):
    """Test that execute method raises CommandTimeoutError when command times out"""
    # Arrange
    mock_client_instance = MagicMock()
    mock_sshclient.return_value = mock_client_instance
    
    # Mock a command that never completes
    stdout_mock = MagicMock()
    stdout_mock.channel.exit_status_ready.return_value = False
    stderr_mock = MagicMock()
    
    mock_client_instance.exec_command.return_value = (None, stdout_mock, stderr_mock)
    mock_select.return_value = ([], [], [])  # No ready channels
    
    SSHConnection.connect()
    
    # Act & Assert
    with pytest.raises(CommandTimeoutError):
        SSHConnection.execute("long_running_command", timeout=1)

@patch("paramiko.SSHClient")
def test_execute_command_calls_exec_command(self, mock_sshclient, SSHConnection):
    """Test that execute method calls paramiko exec_command with correct parameters"""
    # Arrange
    mock_client_instance = MagicMock()
    mock_sshclient.return_value = mock_client_instance
    
    stdout_mock = MagicMock()
    stdout_mock.channel.exit_status_ready.return_value = True
    stdout_mock.channel.recv_exit_status.return_value = 0
    stdout_mock.readlines.return_value = []
    stderr_mock = MagicMock()
    stderr_mock.readlines.return_value = []
    
    mock_client_instance.exec_command.return_value = (None, stdout_mock, stderr_mock)
    
    SSHConnection.connect()
    
    # Act
    SSHConnection.execute("test command")
    
    # Assert
    mock_client_instance.exec_command.assert_called_once_with("test command")
