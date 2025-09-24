import pytest
from unittest.mock import patch, MagicMock
import paramiko
from vm_connection import VMConnectionError

class TestReconnectFunctionality:
    """Comprehensive tests for reconnection functionality"""
    
    @patch("time.sleep", return_value=None)
    @patch("paramiko.SSHClient")
    def test_reconnect_retries_and_succeeds(self, mock_sshclient, mock_sleep, ssh_connection):
        """Test successful reconnection after initial failure"""
        mock_client = MagicMock()
        mock_sshclient.return_value = mock_client
        mock_client.connect.side_effect = [paramiko.SSHException("fail"), None]
        
        result = ssh_connection.reconnect(retries=2, delay=1)
        
        assert result is True
        assert mock_client.connect.call_count == 2
        mock_sleep.assert_called_once_with(1)
    
    @patch("time.sleep", return_value=None)
    def test_reconnect_all_attempts_fail(self, mock_sleep, ssh_connection):
        """Test reconnect when all retry attempts fail"""
        with patch.object(ssh_connection, 'connect', side_effect=VMConnectionError("Connection failed")):
            result = ssh_connection.reconnect(retries=3, delay=0.5)
            
            assert result is False
            assert mock_sleep.call_count == 2  # sleeps between attempts, not after last
    
    @patch("time.sleep", return_value=None)
    def test_reconnect_first_attempt_succeeds(self, mock_sleep, ssh_connection):
        """Test reconnect when first attempt succeeds"""
        with patch.object(ssh_connection, 'connect', return_value=None):
            result = ssh_connection.reconnect(retries=3, delay=1)
            
            assert result is True
            mock_sleep.assert_not_called()  # No sleep needed
    
    def test_reconnect_closes_existing_connection(self, ssh_connection):
        """Test that reconnect properly closes existing connection before retrying"""
        mock_client = MagicMock()
        ssh_connection.client = mock_client
        
        with patch.object(ssh_connection, 'connect', return_value=None) as mock_connect:
            result = ssh_connection.reconnect(retries=1)
            
            # Should close existing connection first
            mock_client.close.assert_called()
            mock_connect.assert_called_once()
            assert result is True
    
    @patch("time.sleep", return_value=None)
    def test_reconnect_with_different_exception_types(self, mock_sleep, ssh_connection):
        """Test reconnect handles different types of connection exceptions"""
        from vm_connection import AuthenticationError
        
        exceptions = [
            AuthenticationError("Auth failed"),
            OSError("Network unreachable"),
            None  # Success on third attempt
        ]
        
        with patch.object(ssh_connection, 'connect', side_effect=exceptions):
            result = ssh_connection.reconnect(retries=3, delay=0.1)
            
            assert result is True
            assert mock_sleep.call_count == 2
