class VMConnectionError(Exception):
    def __init__(self, message: str, original_error=None):
        super().__init__(message)
        self.original_error = original_error

    def __str__(self):
        if self.original_error:
            return f"{super().__str__()} (Original: {self.original_error})"
        return super().__str__()


class CommandTimeoutError(Exception):
    def __init__(self, command: str, timeout: int):
        self.command = command
        self.timeout = timeout
        super().__init__(f"Command '{command}' timed out after {timeout} seconds")


class VMRebootDetectedError(Exception):
    def __init__(self, message: str = "Unexpected VM reboot detected"):
        super().__init__(message)


class VMNotAliveError(Exception):
    def __init__(self, message: str = "VM is not alive or responsive"):
        super().__init__(message)


class VMStateError(Exception):
    def __init__(self, message: str, state_info=None):
        super().__init__(message)
        self.state_info = state_info


class AuthenticationError(VMConnectionError):
    def __init__(self, message: str = "SSH authentication failed"):
        super().__init__(message)