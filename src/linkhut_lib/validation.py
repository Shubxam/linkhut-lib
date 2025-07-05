from datetime import date, datetime

from .exceptions import InvalidTagFormatError


def validate_tag(name: str) -> str:
        """Ensure tag name is alphanumeric and not empty."""
        if not name.replace("-", "").replace("_", "").isalnum():
            raise InvalidTagFormatError(f"Invalid characters present in tag name: {name}")
        return name


def validate_date(cls, datetime_obj: datetime | str | date) -> datetime:
        """Ensure date is a valid datetime object or string."""
        datetime_object: datetime
        if isinstance(datetime_obj, str):
            try:
                datetime_object: datetime = datetime.fromisoformat(datetime_obj)
            except ValueError as e:
                raise ValueError(f"Invalid date string format: {datetime_obj}") from e
        elif isinstance(datetime_obj, datetime):
            datetime_object: datetime = datetime_obj
        elif isinstance(datetime_obj, date):
            datetime_object: datetime = datetime.fromisoformat(datetime_obj.isoformat())
        else:
            raise TypeError("Date must be a datetime object or an ISO formatted string.")
        # if datetime_object > datetime.now(UTC):
        #     raise ValueError("Date cannot be in the future.")
        return datetime_object