class LinkHutError(Exception):
    """Base exception for all LinkHut operations"""
    pass


class InvalidURLError(LinkHutError):
    """Raised when URL format is invalid"""
    pass


class BookmarkNotFoundError(LinkHutError):
    """Raised when bookmark doesn't exist"""
    pass


class InvalidDateFormatError(LinkHutError):
    """Raised when date format is invalid"""
    pass


class InvalidTagFormatError(LinkHutError):
    """Raised when tag format is invalid"""
    pass


class APIError(LinkHutError):
    """Raised when API returns an error"""
    def __init__(self, message: str, status_code: int | None = None, response_data: dict[str, str] | None = None):
        super().__init__(message)
        self.status_code: int | None = status_code
        self.response_data: dict[str, str] | None = response_data
    
    def __str__(self) -> str:
        if self.status_code:
            return f"API Error {self.status_code}: {super().__str__()}"
        return super().__str__()


class BookmarkExistsError(LinkHutError):
    """Raised when trying to create a bookmark that already exists"""
    pass