# VM Connection Module

A resilient Python module for managing SSH connections to remote Linux VMs with advanced health monitoring and recovery capabilities.

## Features
- **Resilient SSH Connections**: Automatic reconnection with retry logic
- **Real-time Command Execution**: Stream command output with timeout support
- **Multi-layer Health Checks**: Network, SSH, and system-level VM monitoring
- **Reboot Detection**: Track VM reboots using kernel boot IDs
## Installation
1. fork the repo then clone it
```bash
git clone < your forked repo link here >
```
2. move into the folder
```bash
cd cloud-linux-submission
```
3. make a new virtual environment (on windows)
```bash
 python -m venv venv
 .\venv\Scripts\activate
```
(on linux / mac)
```bash
 python3 -m venv venv
 source venv/bin/activate
```
4. install required dependencies 
```bash
pip install -r requirements.txt
```
## Testing
Run tests  
```bash 
pytest -q 
``` 
OR 
```bash
pytest -v
```
## what is being tested in edge cases? 
9. Advanced Edge Cases Tests (5 tests)
    * Custom configurations: Non-standard ports, extended timeouts in `test_initialization_with_custom_port_and_timeout`

    * Callback flexibility: Command execution without output callbacks in 
    `test_execute_with_no_output_callback`

    * Invalid parameters: Graceful handling of unsupported health check levels in 
    `test_is_alive_with_invalid_level`

    * Boundary testing: Zero retry scenarios, empty check results
    in `test_reconnect_with_zero_retries`

    * Wrapper robustness: VMConnection behavior with no available health checks in `test_vm_connection_is_alive_with_zero_checks`

## Quick Start

```python
from vm_connection import SSHConnection, VMConnection

# Basic usage
conn = SSHConnection(host="192.168.1.100", user="ubuntu", key_path="~/.ssh/id_rsa")
conn.connect()
exit_code = conn.execute("uptime", timeout=30, output_callback=print)

# High-level VM management
vm = VMConnection("192.168.1.100", "ubuntu", "~/.ssh/id_rsa")
vm.connect()
health = vm.is_alive(level='thorough')
print(f"VM alive: {health['alive']}, confidence: {health['confidence']:.2f}")
```

## Core Classes

### SSHConnection
Low-level SSH operations:
- `connect()`, `execute()`, `reconnect()` - Connection management
- `is_alive(level)` - Health checking with 'basic', 'medium', 'thorough' levels
- `record_boot_id()`, `check_reboot()` - Reboot detection

### VMConnection
High-level wrapper providing enhanced health reporting with confidence scores.

# Design Choices
 ## 1. is_alive() Implementation

Uses layered detection:

* ICMP ping, TCP port behavior, and TCP stack responsiveness

* SSH connectivity and simple command execution

* System-level checks (uptime, disk, memory, processes) in thorough mode

Aggregates results into a confidence score (≥60% with OS signs or ≥70% with SSH required).

## 2. Unexpected Reboot Detection

* Relies on Linux kernel’s boot ID (/proc/sys/kernel/random/boot_id).

* record_boot_id() saves the current ID, check_reboot() compares it later.

* A mismatch raises VMRebootDetectedError.

3. Testing Strategy

* Unit tests with mocks to simulate SSH success/failure, timeouts, and exceptions.

* Integration tests against real or containerized VMs to validate health checks and reboot detection.

----
# How I'd solve long distrubtive commands:

When running a command like a network stress test, I expect that it may disrupt or even break the SSH connection. To handle this, I would design the system as follows:

I would first log the start of the test and its parameters, and run it inside a wrapper script that handles cleanup and sets a completion marker when finished.

I would also store all output locally on the VM (for example in `/var/log/stress_test.log)` so I can review it later even if the SSH session is lost.

For resilient execution, I would use tools such as` nohup, screen, or tmux` so the process continues running independently of the SSH connection. For example:

`nohup ./run_network_stress_test.sh > /var/log/stress_test.log 2>&1 &`

This ensures the test completes even if the session drops, and I can reattach with `screen or tmux` if I want to monitor progress interactively.

If the connection is lost, I would have not assume failure immediately. Instead, I would try reconnecting with exponential backoff and run basic network checks (ping or TCP socket probes) to tell the difference between a disconnection and a full VM crash.

Once the SSH connection is restored, I would verify whether the completion marker exists and review the log file to confirm execution. If the marker is missing or the VM is unresponsive, I would escalate to recovery steps such as rebooting the VM.

I believe this approach ensures the command can run to completion without relying on an uninterrupted SSH session, so it gives me a reliable way to regain control of the VM and check for results afterwards.