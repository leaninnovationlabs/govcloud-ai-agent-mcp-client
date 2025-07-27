class BusinessLogicError(Exception):
    def __init__(self, message: str, code: str = "BUSINESS_LOGIC_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class NotFoundError(BusinessLogicError):
    def __init__(self, resource: str, identifier: str | int):
        message = f"{resource} with ID {identifier} not found"
        super().__init__(message, "NOT_FOUND")


class ValidationError(BusinessLogicError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR") 