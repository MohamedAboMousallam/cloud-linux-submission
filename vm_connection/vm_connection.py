import os
import paramiko
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
    def close(self):
        if self.client:
            self.client.close()
            self.client=None