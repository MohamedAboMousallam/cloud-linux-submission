import pytest
from unittest.mock import patch, MagicMock

@patch("select.select")
@patch("paramiko.SSHClient")
def test_execute_calls_output_callback_for_each_line(mock_sshclient, mock_select, ssh_connection):
    """Test that output_callback is called for each line of streamed output"""
    mock_client = MagicMock()
    mock_sshclient.return_value = mock_client
    
    stdout = MagicMock()
    stdout.channel.exit_status_ready.side_effect = [False, False, False, True]
    stdout.readline.side_effect = ["line1\n", "line2\n", "line3\n", ""]
    stdout.channel.recv_exit_status.return_value = 0
    stdout.readlines.return_value = []
    
    stderr = MagicMock()
    stderr.readlines.return_value = []
    
    mock_client.exec_command.return_value = (None, stdout, stderr)
    mock_select.side_effect = [
        ([stdout.channel], [], []),
        ([stdout.channel], [], []),
        ([stdout.channel], [], []),
        ([], [], [])
    ]
    
    callback_calls = []
    def test_callback(line):
        callback_calls.append(line)
    
    ssh_connection.connect()
    ssh_connection.execute("test command", output_callback=test_callback)
    
    assert callback_calls == ["line1", "line2", "line3"]