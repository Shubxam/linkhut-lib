"""Pydantic models for the LinkHut API and bookmark payloads."""

from datetime import datetime
from enum import StrEnum

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, Json, field_validator

from .exceptions import InvalidTagFormatError
from .validation import validate_date, validate_tag


class Tag(BaseModel):
    """A single bookmark tag."""

    name: str = Field(
        ...,
        description='The name of the tag',
        min_length=1,
        max_length=50,
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, name: str) -> str:
        """Ensure tag name is alphanumeric and not empty."""
        return validate_tag(name)

    def __str__(self) -> str:
        """Return the tag's name string."""
        return self.name


class Date(BaseModel):
    """A bookmark date/time field."""

    date: datetime = Field(
        default_factory=datetime.now,
        description='The date and time',
    )

    @field_validator('date')
    @classmethod
    def validate_date(cls, date: datetime | str) -> datetime:
        """Ensure date is a valid datetime object or string."""
        return validate_date(date)

    def __str__(self) -> str:
        """Return the date in ISO 8601 format."""
        return self.date.isoformat()


class Url(BaseModel):
    """A bookmark URL with Pydantic validation."""

    model_config = ConfigDict(populate_by_name=True)
    url: HttpUrl = Field(..., description='The URL of the bookmark', frozen=True)

    def __str__(self) -> str:
        """Return the URL string (with any normalization, e.g. trailing slash)."""
        return str(self.url)


def validate_url_string(url: str) -> Url:
    """Validate a raw URL string and return a `Url` model.

    Pydantic's `HttpUrl` is stricter than `str`, so constructing it from a
    string needs an explicit conversion. The `# type: ignore` lives here
    instead of at every call site.
    """
    # `HttpUrl` requires an explicit coercion from `str`; Pydantic accepts the
    # dict form without complaint, and ty narrows the input naturally.
    return Url.model_validate({'url': url})


class Bookmark(BaseModel):
    """A LinkHut bookmark with URL, title, tags, notes, and metadata.

    Field aliases match the LinkHut API payload keys (href, description, etc.).
    """

    # without this, the model will not be able to use field names only alias names
    model_config = ConfigDict(populate_by_name=True)

    url: Url = Field(
        ...,
        description='The URL of the bookmark',
        alias='href',
    )
    title: str = Field(
        ..., description='The title of the bookmark', alias='description'
    )
    created_at: Date = Field(
        default_factory=Date,
        description='The date and time when the bookmark was created',
        alias='time',
    )
    note: str = Field(
        '',
        description='An optional note for the bookmark',
        alias='extended',
    )
    hash: str = Field(
        '',
        description='A unique hash for the bookmark, used to identify it',
        repr=False,
    )
    tags: list[Tag] = Field(
        default_factory=list,
        description='A list of tags associated with the bookmark',
        alias='tag',
    )
    public: bool = Field(
        False,
        description='Whether the bookmark is public or not',
        alias='shared',
    )
    toread: bool = Field(
        False,
        description='Whether the bookmark is marked as to-read',
    )

    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, tags: str | list[str] | list[Tag]) -> list[Tag]:
        """Create Tags List from string and Ensure tags are unique and not empty."""
        if isinstance(tags, str):
            # after removing trailing and leading whitespace, if the string is empty, return an empty list
            if not tags.strip():
                return []
            tags_list: list[str] = tags.replace(',', ' ').replace(';', ' ').split()
            return [Tag(name=tag) for tag in set(tags_list)]  # remove duplicates
        if isinstance(tags, list):
            if all(isinstance(tag, str) for tag in tags):
                return [Tag(name=tag) for tag in set(tags)]  # type: ignore
            if all(isinstance(tag, Tag) for tag in set(tags)):
                return tags  # type: ignore
            raise InvalidTagFormatError('Mixed tag types not allowed.')
        raise InvalidTagFormatError(
            'Tags must be a string of space/comma/semicolon separated values, list of strings, or list of Tags.'
        )

    @field_validator('created_at', mode='before')
    @classmethod
    def validate_created_at(cls, created_at: datetime) -> Date:
        """Wrap a raw datetime in the Date pydantic model."""
        return Date(date=created_at)

    @field_validator('url', mode='before')
    @classmethod
    def validate_url(cls, url: str) -> Url:
        """Wrap a raw URL string in the Url pydantic model."""
        return Url(url=url)  # type: ignore

    def __str__(self) -> str:
        """Return a human-readable multi-line bookmark summary."""
        bookmark = f"""
        Bookmark(title={self.title}
        url={self.url.__str__()}
        created_at={self.created_at.__str__()}
        tags={[tag.__str__() for tag in self.tags]})
        """
        return bookmark.strip()


class HTMLResponse(BaseModel):
    """Response model for HTML content (web pages)."""

    # allows assigning arbitrary types to fields, such as BeautifulSoup
    model_config = ConfigDict(arbitrary_types_allowed=True)

    content_soup: BeautifulSoup = Field(..., description='Parsed HTML content')


class APIResponse(BaseModel):
    """Response model for JSON API responses.

    `content_json` is a `pydantic.Json` value, so anything JSON-serializable
    is accepted on input and the parsed Python value (dict / list / scalar)
    is what callers read. Consumers should still narrow the shape themselves
    based on the endpoint that produced the response.
    """

    content_json: Json = Field(..., description='Structured JSON response data')


class GETResponse(BaseModel):
    """Unified response model for HTTP GET requests."""

    status_code: int = Field(..., description='HTTP status code')
    content_type: str = Field(..., description='Content-Type header value')
    url: str = Field(..., description='The requested URL')
    data: HTMLResponse | APIResponse = Field(
        ..., description='Response data based on content type'
    )


class UpdateOutcome(StrEnum):
    """Discriminator for the path an `update_bookmark` call took."""

    UPDATED = 'updated'
    """Strict: bookmark matched, fields written."""
    UPSERTED = 'upserted'
    """Upsert: bookmark did not exist, was created."""
    NO_OP = 'no_op'
    """No field changes were necessary; existing state already matched."""


class CreateOutcome(StrEnum):
    """Discriminator for the path a `create_bookmark` call took."""

    CREATED = 'created'
    """New bookmark created."""
    REPLACED = 'replaced'
    """Existing bookmark replaced (replace=True)."""
    ALREADY_EXISTS = 'already_exists'
    """Existing bookmark left untouched (replace=False; raises in practice)."""


class BookmarkCreateResult(BaseModel):
    """Typed return value of `create_bookmark`.

    `bookmark` is the server-shape payload dict so callers can read fields
    directly without re-parsing the API response. Kept as a dict (not a
    `Bookmark` model) to match the existing `get_bookmarks` shape and avoid
    forcing a wire-format round-trip.
    """

    outcome: CreateOutcome = Field(..., description='Which path the call took.')
    url: str = Field(..., description='The bookmarked URL.')
    bookmark: dict[str, str] = Field(..., description='Server-shape bookmark payload.')


class BookmarkUpdateResult(BaseModel):
    """Typed return value of `update_bookmark` and `upsert_bookmark`.

    Same shape for strict and upsert callers; `outcome` distinguishes the
    paths. `UPSERTED` is only ever produced by `upsert_bookmark`.
    """

    outcome: UpdateOutcome = Field(..., description='Which path the call took.')
    url: str = Field(..., description='The bookmarked URL.')
    bookmark: dict[str, str] = Field(..., description='Server-shape bookmark payload.')
