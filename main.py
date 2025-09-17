from vm_connection import SSHConnection

def log_output_line(line):
    print(f"[REMOTE] {line}")

conn = SSHConnection(
    host="localhost",
    user="tester",
    key_path= r"C:\Users\Mohamed\.ssh\test_id_rsa",
    port=2222
)

try:
    conn.connect()
    print("Connected successfully!")
    
    # Test 1: Basic command with callback
    exit_code = conn.execute("uname -a", output_callback=log_output_line)
    print(f"Exit code: {exit_code}")
    
    # Test 2: Command without callback
    exit_code = conn.execute("whoami")
    print(f"Exit code: {exit_code}")
    
    # Test 3: Command with both stdout and stderr
    exit_code = conn.execute("ls /home /nonexistent", output_callback=log_output_line)
    print(f"Exit code: {exit_code}")
    
    # Test 4: Streaming output over time
    exit_code = conn.execute("for i in {1..5}; do echo \"Line $i\"; sleep 1; done", 
                            output_callback=log_output_line, timeout=10)
    print(f"Exit code: {exit_code}")
    
    # Test 5: Test timeout (this should fail)
    try:
        exit_code = conn.execute("sleep 10", output_callback=log_output_line, timeout=3)
        print(f"Exit code: {exit_code}")
    except TimeoutError as e:
        print(f"Caught timeout as expected: {e}")
    
finally:
    conn.close()
    print("Connection closed.")