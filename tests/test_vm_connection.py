import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vm_connection import VMConnection, VMConnectionError

class TestVMConnection:
    """Test suite for VMConnection wrapper class"""
    
    @pytest.fixture
    def vm_connection(self):
        return VMConnection(
            host="test.example.com",
            user="testuser", 
            key_path="/path/to/key",
            port=22
        )
    
    def test_vm_connection_initialization(self, vm_connection):
        """Test VMConnection initializes with correct parameters"""
        assert vm_connection.ssh.host == "test.example.com"
        assert vm_connection.ssh.user == "testuser"
        assert vm_connection.ssh.key_path == "/path/to/key"
        assert vm_connection.ssh.port == 22
    
    @patch("vm_connection.SSHConnection.connect")
    def test_connect_delegates_to_ssh(self, mock_connect, vm_connection):
        """Test that connect method delegates to SSH connection"""
        vm_connection.connect()
        mock_connect.assert_called_once()
    
    @patch("vm_connection.SSHConnection.close")
    def test_close_delegates_to_ssh(self, mock_close, vm_connection):
        """Test that close method delegates to SSH connection"""
        vm_connection.close()
        mock_close.assert_called_once()
    
    @patch("vm_connection.SSHConnection.execute")
    def test_execute_delegates_to_ssh(self, mock_execute, vm_connection):
        """Test that execute method delegates to SSH connection"""
        mock_execute.return_value = 0
        
        result = vm_connection.execute("test command", timeout=30, output_callback=print)
        
        assert result == 0
        mock_execute.assert_called_once_with("test command", timeout=30, output_callback=print)
    
    @patch("vm_connection.detect_os_activity")
    def test_is_alive_basic_level(self, mock_detect_os, vm_connection):
        """Test is_alive with basic level only does OS detection"""
        def mock_os_activity(host, port, result):
            result['checks_passed'] = 2
            result['checks_failed'] = 1
            return {
                'network_responsive': True,
                'os_active': True,
                'ping_responsive': True
            }
        
        mock_detect_os.side_effect = mock_os_activity
        
        result = vm_connection.is_alive(level='basic')
        
        assert result['alive'] is True
        assert result['confidence'] == 2/3
        assert result['network_reachable'] is True
        assert result['os_signs_detected'] is True
        mock_detect_os.assert_called_once()
    
    @patch("vm_connection.check_ssh_connectivity")
    @patch("vm_connection.detect_os_activity")
    def test_is_alive_medium_level_includes_ssh(self, mock_detect_os, mock_ssh_check, vm_connection):
        """Test is_alive with medium level includes SSH checks"""
        def mock_os_activity(host, port, result):
            result['checks_passed'] = 1
            result['checks_failed'] = 0
            return {'network_responsive': True, 'os_active': False}
        
        def mock_ssh_connectivity(conn, result):
            result['checks_passed'] += 2
            return True
        
        mock_detect_os.side_effect = mock_os_activity
        mock_ssh_check.side_effect = mock_ssh_connectivity
        
        result = vm_connection.is_alive(level='medium')
        
        assert result['alive'] is True  # SSH available + confidence > 0.7
        assert result['confidence'] == 3/3
        assert result['ssh_available'] is True
        mock_detect_os.assert_called_once()
        mock_ssh_check.assert_called_once()
    
    @patch("vm_connection.advanced_os_detection")
    @patch("vm_connection.check_system_services")
    @patch("vm_connection.check_ssh_connectivity")
    @patch("vm_connection.detect_os_activity")
    def test_is_alive_thorough_level_includes_all_checks(self, mock_detect_os, mock_ssh_check, 
                                                        mock_system_services, mock_advanced_os, vm_connection):
        """Test is_alive with thorough level includes all checks"""
        def mock_os_activity(host, port, result):
            result['checks_passed'] = 1
            result['checks_failed'] = 0
            return {'network_responsive': True, 'os_active': True}
        
        def mock_ssh_connectivity(conn, result):
            result['checks_passed'] += 1
            return True
        
        def mock_services(conn, result, level):
            result['checks_passed'] += 2
        
        def mock_advanced(conn, result):
            result['checks_passed'] += 1
        
        mock_detect_os.side_effect = mock_os_activity
        mock_ssh_check.side_effect = mock_ssh_connectivity
        mock_system_services.side_effect = mock_services
        mock_advanced_os.side_effect = mock_advanced
        
        result = vm_connection.is_alive(level='thorough')
        
        assert result['alive'] is True
        assert result['confidence'] == 5/5
        mock_detect_os.assert_called_once()
        mock_ssh_check.assert_called_once()
        mock_system_services.assert_called_once()
        mock_advanced_os.assert_called_once()
    
    @patch("vm_connection.check_ssh_connectivity")
    @patch("vm_connection.detect_os_activity")
    def test_is_alive_thorough_skips_system_checks_when_ssh_unavailable(self, mock_detect_os, mock_ssh_check, vm_connection):
        """Test thorough level skips system checks when SSH is unavailable"""
        def mock_os_activity(host, port, result):
            result['checks_passed'] = 1
            result['checks_failed'] = 0
            return {'network_responsive': True, 'os_active': True}
        
        def mock_ssh_connectivity(conn, result):
            result['checks_failed'] += 1
            result['failed_checks'] = ['SSH failed']
            return False
        
        mock_detect_os.side_effect = mock_os_activity
        mock_ssh_check.side_effect = mock_ssh_connectivity
        
        result = vm_connection.is_alive(level='thorough')
        
        assert result['ssh_available'] is False
        assert 'System services check skipped - SSH unavailable' in result['failed_checks']
        assert 'Advanced OS detection skipped - SSH unavailable' in result['failed_checks']
    
    @patch("vm_connection.detect_os_activity")
    def test_is_alive_returns_false_when_no_evidence(self, mock_detect_os, vm_connection):
        """Test is_alive returns False when there's no evidence of life"""
        def mock_os_activity(host, port, result):
            result['checks_passed'] = 0
            result['checks_failed'] = 3
            result['failed_checks'] = ['All checks failed']
            return {'network_responsive': False, 'os_active': False}
        
        mock_detect_os.side_effect = mock_os_activity
        
        result = vm_connection.is_alive(level='basic')
        
        assert result['alive'] is False
        assert result['confidence'] == 0.0
        assert result['network_reachable'] is False
        assert result['os_signs_detected'] is False