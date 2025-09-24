import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import subprocess
import socket
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vm_connection import (
    detect_os_activity, _test_ping_internal, analyze_port_behavior, _test_tcp_stack_internal,
    check_ssh_connectivity, check_system_services, advanced_os_detection,
    SSHConnection, CommandTimeoutError
)

class TestHealthCheckFunctions:
    """Test suite for individual health check functions"""
    
    def test_detect_os_activity_aggregates_results_correctly(self):
        """Test that detect_os_activity properly aggregates multiple check results"""
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        with patch('vm_connection._test_ping_internal', return_value=True), \
             patch('vm_connection.analyze_port_behavior', return_value={'quick_rejection': True}), \
             patch('vm_connection._test_tcp_stack_internal', return_value=True):
            
            detection = detect_os_activity("test.com", 22, result)
            
            assert detection['os_active'] is True
            assert detection['network_responsive'] is True
    
    @patch('subprocess.run')
    def test_ping_success_on_windows(self, mock_subprocess):
        """Test successful ping on Windows"""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Reply from 192.168.1.1: bytes=32 time=1ms TTL=64"
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        detection_result = {'ping_responsive': False, 'response_pattern': 'timeout'}
        
        with patch('platform.system', return_value='Windows'):
            success = _test_ping_internal("192.168.1.1", result, detection_result)
        
        assert success is True
        assert detection_result['ping_responsive'] is True
        assert detection_result['response_pattern'] == 'normal'
        assert result['checks_passed'] == 1
    
    @patch('subprocess.run')
    def test_ping_failure(self, mock_subprocess):
        """Test ping failure"""
        mock_subprocess.return_value.returncode = 1
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        detection_result = {'ping_responsive': False}
        
        success = _test_ping_internal("unreachable.com", result, detection_result)
        
        assert success is False
        assert detection_result['ping_responsive'] is False
        assert result['checks_failed'] == 1
        assert 'VM not responding to ping' in result['failed_checks']
    
    @patch('subprocess.run')
    def test_ping_timeout_exception(self, mock_subprocess):
        """Test ping command timeout"""
        mock_subprocess.side_effect = subprocess.TimeoutExpired(['ping'], 8)
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        detection_result = {'ping_responsive': False}
        
        success = _test_ping_internal("test.com", result, detection_result)
        
        assert success is False
        assert result['checks_failed'] == 1
    
    @patch('socket.socket')
    def test_analyze_port_behavior_quick_rejection(self, mock_socket):
        """Test port behavior analysis with quick rejections"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.connect_ex.return_value = 111  # Connection refused
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        detection_result = {'port_behavior': 'unknown'}
        
        with patch('time.time', side_effect=[0, 0.1, 0, 0.1, 0, 0.1]):  # Quick responses
            port_analysis = analyze_port_behavior("test.com", 22, result, detection_result)
        
        assert port_analysis['quick_rejection'] is True
        assert detection_result['port_behavior'] == 'quick_rejection'
        assert result['checks_passed'] == 1
    
    @patch('socket.socket')
    def test_analyze_port_behavior_all_timeout(self, mock_socket):
        """Test port behavior when all ports timeout"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.connect_ex.side_effect = socket.timeout()
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        detection_result = {'port_behavior': 'unknown'}
        
        port_analysis = analyze_port_behavior("test.com", 22, result, detection_result)
        
        assert port_analysis['quick_rejection'] is False
        assert detection_result['port_behavior'] == 'all_timeout'
        assert result['checks_failed'] == 1
    
    @patch('socket.socket')
    def test_tcp_stack_responsiveness(self, mock_socket):
        """Test TCP stack responsiveness detection"""
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.connect_ex.return_value = 111  # Connection refused
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        detection_result = {'tcp_stack_active': False}
        
        with patch('time.time', side_effect=[0, 0.1, 0, 0.1, 0, 0.1]):  # Quick responses
            tcp_active = _test_tcp_stack_internal("test.com", 22, result, detection_result)
        
        assert tcp_active is True
        assert detection_result['tcp_stack_active'] is True
        assert result['checks_passed'] == 1

class TestSSHHealthChecks:
    """Test SSH-related health check functions"""
    
    @pytest.fixture
    def mock_ssh_connection(self):
        conn = MagicMock()
        conn.client = MagicMock()
        conn.execute = MagicMock()
        return conn
    
    def test_check_ssh_connectivity_success(self, mock_ssh_connection):
        """Test successful SSH connectivity check"""
        mock_ssh_connection.client.get_transport.return_value.is_active.return_value = True
        mock_ssh_connection.execute.return_value = 0
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        ssh_ok = check_ssh_connectivity(mock_ssh_connection, result)
        
        assert ssh_ok is True
        assert result['checks_passed'] == 2  # Connection + command execution
        mock_ssh_connection.execute.assert_called_once_with('echo "health_check"', timeout=5)
    
    def test_check_ssh_connectivity_reconnect_needed(self, mock_ssh_connection):
        """Test SSH connectivity when reconnection is needed"""
        mock_ssh_connection.client.get_transport.return_value = None
        mock_ssh_connection.connect.return_value = None
        mock_ssh_connection.execute.return_value = 0
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        ssh_ok = check_ssh_connectivity(mock_ssh_connection, result)
        
        assert ssh_ok is True
        assert result['checks_passed'] == 2
        mock_ssh_connection.connect.assert_called_once()
    
    def test_check_ssh_connectivity_command_timeout(self, mock_ssh_connection):
        """Test SSH connectivity when command times out"""
        mock_ssh_connection.client.get_transport.return_value.is_active.return_value = True
        mock_ssh_connection.execute.side_effect = CommandTimeoutError("echo", 5)
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        ssh_ok = check_ssh_connectivity(mock_ssh_connection, result)
        
        assert ssh_ok is False
        assert result['checks_failed'] == 1
        assert 'SSH command timed out' in result['failed_checks']
    
    def test_check_system_services_medium_level(self, mock_ssh_connection):
        """Test system services check at medium level"""
        mock_ssh_connection.execute.return_value = 0
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        check_system_services(mock_ssh_connection, result, level='medium')
        
        assert result['checks_passed'] == 3  # uptime, df, ps
        assert mock_ssh_connection.execute.call_count == 3
    
    def test_check_system_services_thorough_level(self, mock_ssh_connection):
        """Test system services check at thorough level"""
        mock_ssh_connection.execute.return_value = 0
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        check_system_services(mock_ssh_connection, result, level='thorough')
        
        assert result['checks_passed'] == 6  # All checks including memory, who, systemctl
        assert mock_ssh_connection.execute.call_count == 6
    
    def test_check_system_services_with_failures(self, mock_ssh_connection):
        """Test system services check with some failures"""
        mock_ssh_connection.execute.side_effect = [0, 1, 0]  # Mixed results
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        check_system_services(mock_ssh_connection, result, level='medium')
        
        assert result['checks_passed'] == 2
        assert result['checks_failed'] == 1
        assert len(result['failed_checks']) == 1
    
    def test_advanced_os_detection(self, mock_ssh_connection):
        """Test advanced OS detection via SSH"""
        mock_ssh_connection.execute.return_value = 0
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        advanced_os_detection(mock_ssh_connection, result)
        
        assert result['checks_passed'] == 3  # kernel, uname, os-release
        assert mock_ssh_connection.execute.call_count == 3
    
    def test_check_system_services_no_client(self):
        """Test system services check when no SSH client available"""
        mock_conn = MagicMock()
        mock_conn.client = None
        
        result = {'checks_passed': 0, 'checks_failed': 0, 'failed_checks': []}
        
        check_system_services(mock_conn, result)
        
        # Should return early without doing anything
        assert result['checks_passed'] == 0
        assert result['checks_failed'] == 0