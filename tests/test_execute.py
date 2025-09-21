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
