from common.enum.error_code import APIError

class BusinessError(Exception):
    def __init__(self, error_enum: APIError, message=None):
        self.error_enum = error_enum
        self.message = message if message else error_enum.message
        super().__init__(self.message)