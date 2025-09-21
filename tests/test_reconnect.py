from unittest.mock import patch, MagicMock
import paramiko

@patch("time.sleep", return_value=None)
@patch("paramiko.SSHClient")
def test_reconnect_retries_and_succeeds(mock_sshclient, mock_sleep, ssh_connection):
    mock_client = MagicMock()
    mock_sshclient.return_value = mock_client
    mock_client.connect.side_effect = [paramiko.SSHException("fail"), None]
    result = ssh_connection.reconnect(retries=2, delay=1)
    assert result is True
    assert mock_client.connect.call_count == 2
