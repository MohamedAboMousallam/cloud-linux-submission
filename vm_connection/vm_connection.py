import os
import paramiko
import select
import time
from .exceptions import VMConnectionError, CommandTimeoutError, VMRebootDetectedError, AuthenticationError

class SSHConnection:
    def __init__(self, host: str, user:str, key_path:str, port: int, connection_timeout: int = 10 ):
        self.host = host
        self.user = user
        self.key_path = key_path
        self.port = port
        self.connection_timeout= connection_timeout
        self.client = None
    
    def connect(self):
        """open a ssh using the parameters which was stored"""
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
            self.client=None

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
        
        # Get any remaining output
        for line in stdout.readlines():
            if output_callback:
                output_callback(line.strip())
        
        for line in stderr.readlines():
            if output_callback:
                output_callback(f"STDERR: {line.strip()}")
        
        return stdout.channel.recv_exit_status()
    