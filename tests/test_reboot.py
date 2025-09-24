import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vm_connection import VMRebootDetectedError, SSHConnection, VMConnectionError

class TestRebootDetection:
    """Comprehensive tests for reboot detection functionality"""
    
    @pytest.fixture
    def connected_ssh(self, ssh_connection):
        ssh_connection.client = MagicMock()
        return ssh_connection
    
    @patch.object(SSHConnection, "_get_boot_id")
    def test_check_reboot_detects_reboot(self, mock_get_boot_id, connected_ssh):
        """Test that reboot is detected when boot ID changes"""
        mock_get_boot_id.return_value = "new-boot-id"
        connected_ssh.last_boot_id = "old-boot-id"
        
        with pytest.raises(VMRebootDetectedError, match="VM reboot detected"):
            connected_ssh.check_reboot()
    
    @patch.object(SSHConnection, "_get_boot_id")
    def test_check_reboot_no_reboot_detected(self, mock_get_boot_id, connected_ssh):
        """Test that no exception is raised when boot ID hasn't changed"""
        boot_id = "same-boot-id-123"
        mock_get_boot_id.return_value = boot_id
        connected_ssh.last_boot_id = boot_id
        
        # Should not raise any exception
        connected_ssh.check_reboot()
    
    @patch("paramiko.SSHClient")
    def test_record_boot_id_success(self, mock_sshclient, ssh_connection):
        """Test successful boot ID recording"""
        mock_client = MagicMock()
        mock_sshclient.return_value = mock_client
        
        stdout_mock = MagicMock()
        stdout_mock.read.return_value = b"abc123-def456-ghi789"
        stderr_mock = MagicMock()
        stderr_mock.read.return_value = b""
        
        mock_client.exec_command.return_value = (None, stdout_mock, stderr_mock)
        
        ssh_connection.connect()
        ssh_connection.record_boot_id()
        
        assert ssh_connection.last_boot_id == "abc123-def456-ghi789"
        mock_client.exec_command.assert_called_with("cat /proc/sys/kernel/random/boot_id")
    
    def test_get_boot_id_empty_response(self, connected_ssh):
        """Test _get_boot_id when command returns empty response"""
        stdout_mock = MagicMock()
        stdout_mock.read.return_value = b""  # Empty response
        stderr_mock = MagicMock()
        stderr_mock.read.return_value = b"No such file or directory"
        
        connected_ssh.client.exec_command.return_value = (None, stdout_mock, stderr_mock)
        
        with pytest.raises(VMConnectionError, match="Failed to get boot ID"):
            connected_ssh._get_boot_id()
    
    def test_get_boot_id_whitespace_handling(self, connected_ssh):
        """Test that _get_boot_id properly strips whitespace"""
        stdout_mock = MagicMock()
        stdout_mock.read.return_value = b"  abc123-def456-ghi789  \n"
        stderr_mock = MagicMock()
        stderr_mock.read.return_value = b""
        
        connected_ssh.client.exec_command.return_value = (None, stdout_mock, stderr_mock)
        
        boot_id = connected_ssh._get_boot_id()
        assert boot_id == "abc123-def456-ghi789"
    
    @patch.object(SSHConnection, "_get_boot_id")
    def test_check_reboot_propagates_get_boot_id_errors(self, mock_get_boot_id, connected_ssh):
        """Test that check_reboot propagates errors from _get_boot_id (except reboot detection)"""
        connected_ssh.last_boot_id = "some-boot-id"
        mock_get_boot_id.side_effect = VMConnectionError("SSH command failed")
        
        with pytest.raises(VMConnectionError, match="SSH command failed"):
            connected_ssh.check_reboot()
