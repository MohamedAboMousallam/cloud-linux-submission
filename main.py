from vm_connection import SSHConnection

conn = SSHConnection(
    host="localhost",
    user="tester",
    key_path= r"C:\Users\Mohamed\.ssh\test_id_rsa",
    port=2222
)
conn.connect()
print("Connected successfully!")
stdin, stdout, stderr = conn.client.exec_command("uname -a")
print(stdout.read().decode())
conn.close()