class AppError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "INVALID_REQUEST"):
        super().__init__(message)
        self.status = status
        self.code = code


class DocumentError(AppError):
    pass
