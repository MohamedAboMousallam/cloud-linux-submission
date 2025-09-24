"""
vm_connection.py

A resilient Python module for managing SSH connections to remote Linux VMs.
It provides functionality to connect, execute commands with real-time output,
detect unexpected reboots, and handle reconnections.

Example:
    conn = SSHConnection(host="192.168.1.10", user="tester", key_path="/path/to/key")
    conn.connect()
    exit_code = conn.execute("uptime", timeout=30, output_callback=print)
"""
import os
import paramiko
import paramiko.buffered_pipe
import time
import select
import logging
import subprocess
import socket
import platform

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class VMConnectionError(Exception):
    def __init__(self, message: str, original_error=None):
        super().__init__(message)
        self.original_error = original_error

class CommandTimeoutError(VMConnectionError):
    def __init__(self, command: str, timeout: int):
        super().__init__(f"Command '{command}' timed out after {timeout} seconds")
        self.command = command
        self.timeout = timeout

class VMRebootDetectedError(VMConnectionError):
    def __init__(self, message: str = "Unexpected VM reboot detected"):
        super().__init__(message)

class AuthenticationError(VMConnectionError):
    def __init__(self, message: str = "SSH authentication failed"):
        super().__init__(message)


# ============================================================================
# HEALTH CHECKS
# ============================================================================

class HealthCheckConfig:
    """Configuration constants for health checks."""
    DEFAULT_PING_COUNT = 3
    DEFAULT_PING_TIMEOUT = 1
    DEFAULT_PING_PROCESS_TIMEOUT = 8
    
    DEFAULT_SOCKET_TIMEOUT = 2.0
    QUICK_RESPONSE_THRESHOLD = 0.5
    MIN_QUICK_REJECTIONS = 2
    
    DEFAULT_TCP_TESTS = 3
    MIN_QUICK_TCP_RESPONSES = 2
    
    DEFAULT_TEST_PORTS = [22, 80, 443]
    
    ALIVE_CONFIDENCE_THRESHOLD = 0.6
    SSH_CONFIDENCE_THRESHOLD = 0.7

def detect_os_activity(host, port, result):
    """
    This is part of my solution to check if a VM Is alive if the SSH isn't available Perform multi-layer detection to infer if the VM's operating system is still running.
    This function combines three tiers of network-level checks:
        1. ICMP ping test
        2. TCP port behavior analysis
        3. TCP stack responsiveness
    The results are aggregated into a confidence score to decide whether the VM's OS
    is likely active, even if the SSH service itself is unavailable.
    Args:
        host (str): Hostname or IP address of the VM to test.
        port (int): Primary port associated with the service (e.g., SSH port).
        result (dict): Shared result object tracking checks passed, failed, and messages.
    Returns:
        dict: A dictionary containing detailed detection results with keys:
            - network_responsive (bool): Whether any positive signal was detected.
            - os_active (bool): Whether the VM OS is likely still running.
            - ping_responsive (bool): ICMP ping success.
            - port_behavior (str): One of "quick_rejection", "mixed_response", "all_timeout", "unknown".
            - tcp_stack_active (bool): Whether TCP stack appeared responsive.
            - response_pattern (str): Additional details, e.g., "normal", "timeout".
    """
    detection_result = {
        'network_responsive': False,
        'os_active': False,
        'ping_responsive': False,
        'port_behavior': 'unknown',
        'tcp_stack_active': False,
        'response_pattern': 'timeout'
    }

    # Tier 1: ICMP ping
    ping_success = test_ping(host, result, detection_result)

    # Tier 2: TCP port behavior
    port_analysis = analyze_port_behavior(host, port, result, detection_result)

    # Tier 3: TCP stack responsiveness
    tcp_stack_active = test_tcp_stack(host, port, result, detection_result)

    # Aggregate evidence
    os_indicators = 0
    if ping_success:
        os_indicators += 2
    if port_analysis.get('quick_rejection', False):
        os_indicators += 2
    if tcp_stack_active:
        os_indicators += 1

    detection_result['os_active'] = os_indicators >= 2
    detection_result['network_responsive'] = os_indicators >= 1

    return detection_result


def test_ping(host, result, detection_result):
    """Test basic ICMP connectivity."""
    try:
        if platform.system().lower().startswith('win'):
            cmd = ['ping', '-n', str(HealthCheckConfig.DEFAULT_PING_COUNT), '-w', str(HealthCheckConfig.DEFAULT_PING_TIMEOUT * 1000), host]
        else:
            cmd = ['ping', '-c', str(HealthCheckConfig.DEFAULT_PING_COUNT), '-W', str(HealthCheckConfig.DEFAULT_PING_TIMEOUT), host]

        ping_result = subprocess.run(cmd, capture_output=True, timeout=HealthCheckConfig.DEFAULT_PING_PROCESS_TIMEOUT, text=True)

        if ping_result.returncode == 0:
            result['checks_passed'] += 1
            detection_result['ping_responsive'] = True

            output = ping_result.stdout.lower()
            if 'ttl=' in output:
                detection_result['response_pattern'] = 'normal'
            return True
        else:
            result['checks_failed'] += 1
            result['failed_checks'].append('VM not responding to ping')
            return False
    except Exception as e:
        result['checks_failed'] += 1
        result['failed_checks'].append(f'Ping test failed: {e}')
        return False


def analyze_port_behavior(host, port, result, detection_result):
    """Check how the VM responds to TCP connection attempts."""
    port_analysis = {'quick_rejection': False, 'any_response': False}
    test_ports = [port] + HealthCheckConfig.DEFAULT_TEST_PORTS

    quick_rejections = 0
    for p in test_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(HealthCheckConfig.DEFAULT_SOCKET_TIMEOUT)
            start_time = time.time()
            res = sock.connect_ex((host, p))
            elapsed = time.time() - start_time
            if res == 0:
                port_analysis['any_response'] = True
            elif elapsed < HealthCheckConfig.QUICK_RESPONSE_THRESHOLD:
                quick_rejections += 1
                port_analysis['any_response'] = True
            sock.close()
        except Exception:
            continue

    if quick_rejections >= HealthCheckConfig.MIN_QUICK_REJECTIONS:
        port_analysis['quick_rejection'] = True
        detection_result['port_behavior'] = 'quick_rejection'
        result['checks_passed'] += 1
    elif port_analysis['any_response']:
        detection_result['port_behavior'] = 'mixed_response'
        result['checks_passed'] += 1
    else:
        detection_result['port_behavior'] = 'all_timeout'
        result['checks_failed'] += 1
        result['failed_checks'].append('All ports timeout - likely VM shutdown')

    return port_analysis


def test_tcp_stack(host, port, result, detection_result):
    """Test TCP stack responsiveness."""
    try:
        responses = []
        for _ in range(HealthCheckConfig.DEFAULT_TCP_TESTS):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(HealthCheckConfig.DEFAULT_PING_TIMEOUT)
            try:
                start = time.time()
                code = sock.connect_ex((host, port))
                elapsed = time.time() - start
                responses.append((code, elapsed))
            finally:
                sock.close()
        quick_responses = sum(1 for _, t in responses if t < HealthCheckConfig.QUICK_RESPONSE_THRESHOLD)
        if quick_responses >= HealthCheckConfig.MIN_QUICK_TCP_RESPONSES:
            detection_result['tcp_stack_active'] = True
            result['checks_passed'] += 1
            return True
        else:
            result['checks_failed'] += 1
            return False
    except Exception as e:
        result['checks_failed'] += 1
        result['failed_checks'].append(f'TCP stack test failed: {e}')
        return False


# ============================================================================
# SSH CHECKS
# ============================================================================

def check_ssh_connectivity(conn, result):
    """
    Check SSH connectivity by verifying the client is active and executing a simple command.
    Returns True if SSH is working, False otherwise.
    """
    try:
        # Check if existing connection is active
        transport = conn.client.get_transport() if conn.client else None
        if transport and transport.is_active():
            result['checks_passed'] += 1
        else:
            # Try to reconnect
            try:
                conn.connect()
                result['checks_passed'] += 1
            except Exception as e:
                result['failed_checks'].append(f'SSH connection failed: {str(e)}')
                result['checks_failed'] += 1
                return False

        # Test simple command execution
        try:
            exit_code = conn.execute('echo "health_check"', timeout=5)
            if exit_code == 0:
                result['checks_passed'] += 1
                return True
            else:
                result['failed_checks'].append(f'Basic SSH command failed: exit {exit_code}')
                result['checks_failed'] += 1
                return False
        except CommandTimeoutError:
            result['failed_checks'].append('SSH command timed out')
            result['checks_failed'] += 1
            return False

    except Exception as e:
        result['failed_checks'].append(f'SSH check failed: {str(e)}')
        result['checks_failed'] += 1
        return False


def check_system_services(conn, result, level='medium'):
    """
    Check system-level services and health indicators via SSH.
    This can be extended to check disk, memory, processes, uptime, etc.
    """
    if not conn.client:
        return

    services_to_check = [
        ('uptime', 'System uptime check'),
        ('df -h /', 'Disk space check'),
        ('ps aux | head -5', 'Process list check')
    ]

    if level == 'thorough':
        services_to_check.extend([
            ('free -m', 'Memory usage check'),
            ('who', 'User session check'),
            ('systemctl is-system-running 2>/dev/null || echo "unknown"', 'System state check')
        ])

    for command, description in services_to_check:
        try:
            exit_code = conn.execute(command, timeout=5)
            if exit_code == 0:
                result['checks_passed'] += 1
            else:
                result['failed_checks'].append(f'{description} failed')
                result['checks_failed'] += 1
        except Exception as e:
            result['failed_checks'].append(f'{description} error: {str(e)}')
            result['checks_failed'] += 1


def advanced_os_detection(conn, result):
    """
    Advanced OS detection using SSH to read kernel, OS release, and system info.
    """
    if not conn.client:
        return

    os_indicators = [
        ('cat /proc/version 2>/dev/null | head -1', 'Linux kernel check'),
        ('uname -a', 'System info check'),
        ('cat /etc/os-release 2>/dev/null | head -3', 'OS release check')
    ]

    for command, description in os_indicators:
        try:
            exit_code = conn.execute(command, timeout=3)
            if exit_code == 0:
                result['checks_passed'] += 1
            else:
                result['checks_failed'] += 1
        except Exception:
            result['checks_failed'] += 1


# ============================================================================
# SSH CONNECTION CLASS
# ============================================================================

class SSHConnection:
    """
    Represents a resilient SSH connection to a remote Linux VM.

    Responsibilities:
    - Establish and maintain an SSH session using Paramiko
    - Execute shell commands with real-time output streaming
    Args:
        host (str): Hostname or IP address of the VM.
        user (str): SSH username.
        key_path (str): Path to the SSH private key.
        port (int, optional): SSH port (default: 22).
    """
    def __init__(self, host: str, user: str, key_path: str, port: int = 22, connection_timeout: int = 10):
        self.host = host
        self.user = user
        self.key_path = key_path
        self.port = port
        self.connection_timeout = connection_timeout
        self.client = None
        self.last_boot_id = None

    def connect(self):
        """Open a SSH connection using the stored parameters"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if self.key_path:
                client.connect(
                    hostname=self.host,
                    username=self.user,
                    port=self.port,
                    key_filename=os.path.expanduser(self.key_path),
                    timeout=self.connection_timeout
                )
            else:
                raise ValueError("Key_path is required for connecting to the vm using key-based authenticating")
            self.client = client
        except paramiko.AuthenticationException as e:
            raise AuthenticationError("SSH authentication failed") from e
        except (paramiko.SSHException, OSError) as e:
            raise VMConnectionError(f"failed to connect to the VM at {self.host}:{self.port}", e) from e

    def close(self):
        if self.client:
            self.client.close()
            self.client = None

    def execute(self, command, timeout=None, output_callback=None):
        if not self.client:
            raise VMConnectionError("Not connected to VM")

        start_time = time.time()
        _, stdout, stderr = self.client.exec_command(command)

        # Make channels non-blocking
        stdout.channel.setblocking(0)
        stderr.channel.setblocking(0)

        while not stdout.channel.exit_status_ready():
            # Calculate remaining timeout
            if timeout:
                elapsed = time.time() - start_time
                remaining_timeout = timeout - elapsed
                if remaining_timeout <= 0:
                    stdout.channel.close()
                    raise CommandTimeoutError(command, timeout)
                select_timeout = min(1.0, remaining_timeout)  # Check every second max
            else:
                select_timeout = 1.0

            try:
                ready, _, _ = select.select([stdout.channel, stderr.channel], [], [], select_timeout)

                if stdout.channel in ready:
                    try:
                        line = stdout.readline()
                        if line and output_callback:
                            output_callback(line.strip())
                    except:
                        pass  # Channel might be closed

                if stderr.channel in ready:
                    try:
                        line = stderr.readline()
                        if line and output_callback:
                            output_callback(f"STDERR: {line.strip()}")
                    except:
                        pass

            except select.error:
                # Handle select errors (like on Windows)
                break

        # Get any remaining output (with timeout protection)
        try:
            for line in stdout.readlines():
                if output_callback:
                    output_callback(line.strip())
        except (socket.timeout, paramiko.buffered_pipe.PipeTimeout):
            pass  # Channel timed out, ignore remaining output

        try:
            for line in stderr.readlines():
                if output_callback:
                    output_callback(f"STDERR: {line.strip()}")
        except (socket.timeout, paramiko.buffered_pipe.PipeTimeout):
            pass  # Channel timed out, ignore remaining output

        return stdout.channel.recv_exit_status()

    def reconnect(self, retries=3, delay=3):
        for attempt in range(1, retries + 1):
            try:
                self.close()  # ensure old connection is gone
                self.connect()
                return True  # success
            except VMConnectionError:
                if attempt < retries:
                    time.sleep(delay)
                else:
                    return False

    def is_alive(self, level='medium'):
        """Check if VM is alive and responsive using multiple detection methods.

        Args:
            level: 'basic', 'medium', or 'thorough' - determines depth of checks

        Returns:
            bool: True if VM is considered alive, False otherwise
        """
        logger.info(f"Starting VM health check (level: {level}) for {self.host}")

        result = {
            'checks_passed': 0,
            'checks_failed': 0,
            'failed_checks': []
        }

        # Level 1: Network-level OS detection (works even if SSH is down)
        os_detection = detect_os_activity(self.host, self.port, result)
        logger.info(f"OS detection result: {os_detection}")

        # Level 2: SSH connectivity check
        if level in ['medium', 'thorough']:
            ssh_ok = check_ssh_connectivity(self, result)
            if ssh_ok and level == 'thorough':
                # Level 3: System services check
                check_system_services(self, result, level='thorough')

        # Decision logic: VM is alive if we have strong evidence
        total_checks = result['checks_passed'] + result['checks_failed']
        if total_checks == 0:
            logger.warning("No health checks could be performed")
            return False

        success_rate = result['checks_passed'] / total_checks
        is_alive = success_rate >= 0.6 or os_detection['os_active']

        logger.info(f"VM health check complete: {result['checks_passed']}/{total_checks} passed, alive={is_alive}")
        if result['failed_checks']:
            logger.warning(f"Failed checks: {result['failed_checks']}")

        return is_alive

    def record_boot_id(self):
        """Record the current boot ID for reboot detection"""
        if not self.client:
            raise VMConnectionError("Not connected to VM")
        try:
            self.last_boot_id = self._get_boot_id()
            logger.info(f"Boot ID recorded: {self.last_boot_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to record boot ID: {e}")
            raise

    def check_reboot(self):
        """Check if VM has rebooted since last boot ID recording"""
        if not self.client:
            raise VMConnectionError("Not connected to VM")
        if self.last_boot_id is None:
            raise ValueError("Boot ID not recorded yet")

        try:
            current_boot_id = self._get_boot_id()
            if current_boot_id != self.last_boot_id:
                logger.warning(f"VM reboot detected! Old: {self.last_boot_id[:8]}..., New: {current_boot_id[:8]}...")
                raise VMRebootDetectedError("VM reboot detected")
            logger.debug("No reboot detected")
        except Exception as e:
            if "VM reboot detected" in str(e):
                raise
            logger.error(f"Failed to check reboot status: {e}")
            raise

    def _get_boot_id(self):
        """Get the current boot ID from the VM"""
        _, stdout, stderr = self.client.exec_command("cat /proc/sys/kernel/random/boot_id")
        boot_id = stdout.read().decode().strip()
        if not boot_id:
            error = stderr.read().decode().strip()
            raise VMConnectionError(f"Failed to get boot ID: {error}")
        return boot_id



# SSHConnection: Low-level SSH operations
# VMConnection: High-level VM management
# ============================================================================
# VM CONNECTION WRAPPER CLASS
# ============================================================================

class VMConnection:
    """
    High-level wrapper for managing a VM connection and health checks.
    Delegates SSH handling to SSHConnection.
    """
    def __init__(self, host, user, key_path, port=22, connection_timeout=10):
        self.ssh = SSHConnection(host, user, key_path, port, connection_timeout)

    def connect(self):
        """Open SSH connection."""
        self.ssh.connect()

    def close(self):
        """Close SSH connection."""
        self.ssh.close()

    def execute(self, command, timeout=None, output_callback=None):
        """Execute a command over SSH."""
        return self.ssh.execute(command, timeout=timeout, output_callback=output_callback)

    def is_alive(self, level='medium'):
        result = {
            'alive': False,
            'confidence': 0.0,
            'checks_passed': 0,
            'checks_failed': 0,
            'response_time_ms': 0,
            'failed_checks': [],
            'ssh_available': False,
            'network_reachable': False,
            'os_signs_detected': False,
            'detailed_status': {}
        }

        # 1. Always do network-level checks
        detection_result = detect_os_activity(self.ssh.host, self.ssh.port, result)
        result.update(detection_result)
        result['network_reachable'] = detection_result['network_responsive']
        result['os_signs_detected'] = detection_result['os_active']

        # 2. SSH checks for medium and thorough levels (regardless of network status)
        if level in ['medium', 'thorough']:
            ssh_ok = check_ssh_connectivity(self.ssh, result)
            result['ssh_available'] = ssh_ok
            
            # 3. System services only for thorough level
            if level == 'thorough':
                if ssh_ok:
                    check_system_services(self.ssh, result, level='thorough')
                    advanced_os_detection(self.ssh, result)
                else:
                    result['failed_checks'].extend([
                    'System services check skipped - SSH unavailable',
                    'Advanced OS detection skipped - SSH unavailable'])
                    result['checks_failed'] += 2

        # 4. Decision logic
        total_checks = result['checks_passed'] + result['checks_failed']
        if total_checks > 0:
            result['confidence'] = result['checks_passed'] / total_checks
            if result['os_signs_detected'] and result['confidence'] > 0.6:
                result['alive'] = True
            elif result['ssh_available'] and result['confidence'] > 0.7:
                result['alive'] = True

        return result

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'SSHConnection',
    'VMConnection', 
    'VMConnectionError',
    'CommandTimeoutError',
    'VMRebootDetectedError',
    'AuthenticationError'
]