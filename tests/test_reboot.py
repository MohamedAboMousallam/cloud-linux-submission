import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vm_connection import VMRebootDetectedError, SSHConnection

@patch.object(SSHConnection, "_get_boot_id")
def test_check_reboot_detects_reboot(mock_get_boot_id, ssh_connection):
    mock_get_boot_id.return_value = "new-boot-id"
    ssh_connection.last_boot_id = "old-boot-id"
    ssh_connection.client = MagicMock()
    with pytest.raises(VMRebootDetectedError):
        ssh_connection.check_reboot()
