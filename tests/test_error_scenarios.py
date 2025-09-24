import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import paramiko
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vm_connection import (
    SSHConnection, VMConnection, VMConnectionError, CommandTimeoutError, 
    VMRebootDetectedError, AuthenticationError
)

class TestErrorScenarios:
    """Test suite for various error scenarios and edge cases"""
    
    @pytest.fixture
    def ssh_connection(self):
        return SSHConnection(
            host="test.example.com",
            user="testuser", 
            key_path="/path/to/key"
        )
    
    def test_execute_without_connection_raises_error(self, ssh_connection):
        """Test that execute raises error when not connected"""
        with pytest.raises(VMConnectionError, match="Not connected to VM"):
            ssh_connection.execute("test command")
    
    def test_connect_with_authentication_failure(self, ssh_connection):
        """Test connection failure due to authentication"""
        with patch("paramiko.SSHClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.connect.side_effect = paramiko.AuthenticationException("Auth failed")
            
            with pytest.raises(AuthenticationError, match="SSH authentication failed"):
                ssh_connection.connect()
    
    def test_connect_with_ssh_exception(self, ssh_connection):
        """Test connection failure due to SSH exception"""
        with patch("paramiko.SSHClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.connect.side_effect = paramiko.SSHException("SSH error")
            
            with pytest.raises(VMConnectionError, match="failed to connect to the VM"):
                ssh_connection.connect()
    
    def test_connect_with_os_error(self, ssh_connection):
        """Test connection failure due to OS error (network unreachable, etc.)"""
        with patch("paramiko.SSHClient") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            mock_instance.connect.side_effect = OSError("Network unreachable")
            
            with pytest.raises(VMConnectionError, match="failed to connect to the VM"):
                ssh_connection.connect()
    
    def test_connect_without_key_path_raises_error(self, ssh_connection):
        """Test that connect raises error when key_path is None"""
        ssh_connection.key_path = None
        
        with pytest.raises(ValueError, match="Key_path is required"):
            ssh_connection.connect()
    
    def test_connect_with_empty_key_path_raises_error(self, ssh_connection):
        """Test that connect raises error when key_path is empty"""
        ssh_connection.key_path = ""
        
        with pytest.raises(ValueError, match="Key_path is required"):
            ssh_connection.connect()
    
    @patch("paramiko.SSHClient")
    def test_execute_command_timeout_closes_channel(self, mock_sshclient, ssh_connection):
        """Test that execute properly closes channel on timeout"""
        mock_client = MagicMock()
        mock_sshclient.return_value = mock_client
        
        stdout_mock = MagicMock()
        stdout_mock.channel.exit_status_ready.return_value = False
        stderr_mock = MagicMock()
        
        mock_client.exec_command.return_value = (None, stdout_mock, stderr_mock)
        
        ssh_connection.connect()
        
        with patch("time.time", side_effect=[0, 2]):  # Simulate timeout
            with pytest.raises(CommandTimeoutError):
                ssh_connection.execute("long_command", timeout=1)
        
        stdout_mock.channel.close.assert_called_once()
    
    def test_reconnect_all_attempts_fail(self, ssh_connection):
        """Test reconnect when all retry attempts fail"""
        with patch.object(ssh_connection, 'connect', side_effect=VMConnectionError("Failed")):
            result = ssh_connection.reconnect(retries=3, delay=0.1)
            assert result is False
    
    def test_record_boot_id_without_connection(self, ssh_connection):
        """Test record_boot_id raises error when not connected"""
        with pytest.raises(VMConnectionError, match="Not connected to VM"):
            ssh_connection.record_boot_id()
    
    def test_check_reboot_without_connection(self, ssh_connection):
        """Test check_reboot raises error when not connected"""
        with pytest.raises(VMConnectionError, match="Not connected to VM"):
            ssh_connection.check_reboot()
    
    def test_check_reboot_without_recorded_boot_id(self, ssh_connection):
        """Test check_reboot raises error when boot ID not recorded"""
        ssh_connection.client = MagicMock()  # Simulate connection
        
        with pytest.raises(ValueError, match="Boot ID not recorded yet"):
            ssh_connection.check_reboot()
    
    def test_get_boot_id_failure(self, ssh_connection):
        """Test _get_boot_id when command fails"""
        ssh_connection.client = MagicMock()
        
        # Mock exec_command to return empty stdout and error in stderr
        stdout_mock = MagicMock()
        stdout_mock.read.return_value = b""
        stderr_mock = MagicMock()
        stderr_mock.read.return_value = b"Permission denied"
        
        ssh_connection.client.exec_command.return_value = (None, stdout_mock, stderr_mock)
        
        with pytest.raises(VMConnectionError, match="Failed to get boot ID"):
            ssh_connection._get_boot_id()
    
    def test_close_connection_safely(self, ssh_connection):
        """Test that close() works safely even when client is None"""
        ssh_connection.client = None
        ssh_connection.close()  # Should not raise exception
        
        # Test with actual client
        mock_client = MagicMock()
        ssh_connection.client = mock_client
        ssh_connection.close()
        mock_client.close.assert_called_once()
        assert ssh_connection.client is None

class TestVMConnectionErrors:
    """Test error scenarios specific to VMConnection wrapper"""
    
    @pytest.fixture
    def vm_connection(self):
        return VMConnection(
            host="test.example.com",
            user="testuser",
            key_path="/path/to/key"
        )
    
    def test_vm_connection_delegates_errors(self, vm_connection):
        """Test that VMConnection properly delegates errors from SSH layer"""
        with patch.object(vm_connection.ssh, 'connect', side_effect=AuthenticationError("Auth failed")):
            with pytest.raises(AuthenticationError):
                vm_connection.connect()
    
    def test_vm_connection_execute_error_delegation(self, vm_connection):
        """Test that VMConnection execute errors are properly delegated"""
        with patch.object(vm_connection.ssh, 'execute', side_effect=CommandTimeoutError("cmd", 30)):
            with pytest.raises(CommandTimeoutError):
                vm_connection.execute("test command", timeout=30)

class TestEdgeCases:
    """Test various edge cases and boundary conditions"""
    
    @pytest.fixture
    def ssh_connection(self):
        return SSHConnection(
            host="test.example.com",
            user="testuser",
            key_path="/path/to/key"
        )
    
    def test_initialization_with_custom_port_and_timeout(self):
        """Test initialization with custom port and connection timeout"""
        conn = SSHConnection(
            host="custom.host.com",
            user="customuser",
            key_path="/custom/key",
            port=2222,
            connection_timeout=30
        )
        
        assert conn.host == "custom.host.com"
        assert conn.user == "customuser"
        assert conn.key_path == "/custom/key"
        assert conn.port == 2222
        assert conn.connection_timeout == 30
    
    @patch("paramiko.SSHClient")
    def test_execute_with_no_output_callback(self, mock_sshclient, ssh_connection):
        """Test execute works correctly when no output callback is provided"""
        mock_client = MagicMock()
        mock_sshclient.return_value = mock_client
        
        stdout_mock = MagicMock()
        stdout_mock.channel.exit_status_ready.return_value = True
        stdout_mock.channel.recv_exit_status.return_value = 0
        stdout_mock.readlines.return_value = ["output line 1\n", "output line 2\n"]
        
        stderr_mock = MagicMock()
        stderr_mock.readlines.return_value = []
        
        mock_client.exec_command.return_value = (None, stdout_mock, stderr_mock)
        
        ssh_connection.connect()
        exit_code = ssh_connection.execute("test command")  # No callback
        
        assert exit_code == 0
    
    def test_is_alive_with_invalid_level(self, ssh_connection):
        """Test is_alive with invalid level parameter"""
        # Should default to medium behavior for invalid levels
        with patch("vm_connection.detect_os_activity") as mock_detect:
            mock_detect.return_value = {'network_responsive': False, 'os_active': False}
            
            result = ssh_connection.is_alive(level='invalid_level')
            
            # Should still work, treating as medium level
            mock_detect.assert_called_once()
    
    @patch("time.sleep")
    def test_reconnect_with_zero_retries(self, mock_sleep, ssh_connection):
        """Test reconnect behavior with zero retries"""
        with patch.object(ssh_connection, 'connect', side_effect=VMConnectionError("Failed")):
            result = ssh_connection.reconnect(retries=0)
            assert result is False
            mock_sleep.assert_not_called()
    
    def test_vm_connection_is_alive_with_zero_checks(self):
        """Test VMConnection is_alive when no checks can be performed"""
        vm_conn = VMConnection("test.com", "user", "/key")
        
        with patch("vm_connection.detect_os_activity") as mock_detect:
            def mock_os_activity(host, port, result):
                # No checks performed
                return {'network_responsive': False, 'os_active': False}
            
            mock_detect.side_effect = mock_os_activity
            
            result = vm_conn.is_alive()
            
            assert result['alive'] is False
            assert result['confidence'] == 0.0