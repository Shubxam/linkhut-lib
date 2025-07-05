from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .exceptions import InvalidTagFormatError
from .validation import validate_date, validate_tag


class Tag(BaseModel):
    name: str = Field(
        ...,
        description="The name of the tag",
        min_length=1,
        max_length=50,
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        """Ensure tag name is alphanumeric and not empty."""
        return validate_tag(name)

    def __str__(self) -> str:
        return self.name


class Date(BaseModel):
    date: datetime = Field(
        default_factory=datetime.now,
        description="The date and time",
    )

    @field_validator("date")
    @classmethod
    def validate_date(cls, date: datetime | str) -> datetime:
        """Ensure date is a valid datetime object or string."""
        return validate_date(cls, date)
        
    def __str__(self) -> str:
        return self.date.isoformat()


class Url(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    url: HttpUrl = Field(..., description="The URL of the bookmark", frozen=True)

    def __str__(self) -> str:
        return str(self.url)


class Bookmark(BaseModel):
    
    # without this, the model will not be able to use field names only alias names
    model_config = ConfigDict(populate_by_name=True)

    url: Url = Field(
        ...,
        description="The URL of the bookmark",
        alias="href",
    )
    title: str = Field(..., description="The title of the bookmark", alias="description")
    created_at: Date = Field(
        default_factory=Date,
        description="The date and time when the bookmark was created",
        alias="time",
    )
    note: str = Field(
        "",
        description="An optional note for the bookmark",
        alias="extended",
    )
    hash: str = Field(
        "",
        description="A unique hash for the bookmark, used to identify it",
        repr=False,
    )
    tags: list[Tag] = Field(
        default_factory=list,
        description="A list of tags associated with the bookmark",
        alias="tag",
    )
    public: bool = Field(
        False,
        description="Whether the bookmark is public or not",
        alias="shared",
    )
    toread: bool = Field(
        False,
        description="Whether the bookmark is marked as to-read",
    )

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, tags: str | list[str] | list[Tag]) -> list[Tag]:
        """Create Tags List from string and Ensure tags are unique and not empty."""
        if isinstance(tags, str):
            # after removing trailing and leading whitespace, if the string is empty, return an empty list
            if not tags.strip():
                return []
            tags_list: list[str] = tags.replace(",", " ").replace(";", " ").split()
            return [Tag(name=tag) for tag in set(tags_list)]  # remove duplicates
        elif isinstance(tags, list):
            if all(isinstance(tag, str) for tag in tags):
                return [Tag(name=tag) for tag in set(tags)]  # type: ignore
            elif all(isinstance(tag, Tag) for tag in set(tags)):
                return tags  # type: ignore
            else:
                raise InvalidTagFormatError("Mixed tag types not allowed.")
        else:
            raise InvalidTagFormatError(
                "Tags must be a string of space/comma/semicolon separated values, list of strings, or list of Tags."
            )
    
    @field_validator("created_at", mode="before")
    @classmethod
    def validate_created_at(cls, created_at: datetime) -> Date:
        return Date(date=created_at)
    
    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, url: str) -> Url:
        return Url(url=url)  # type: ignore

    def __str__(self) -> str:
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

    content_soup: BeautifulSoup = Field(..., description="Parsed HTML content")

    @field_validator("content_soup")
    @classmethod
    def validate_content(cls, content: BeautifulSoup) -> BeautifulSoup:
        """Ensure content is a BeautifulSoup object."""
        if not isinstance(content, BeautifulSoup):
            raise TypeError("Content must be a string or a BeautifulSoup object.")
        return content


class APIResponse(BaseModel):
    """Response model for JSON API responses."""

    content_json: dict[str, Any] | list[dict[str, Any]] = Field(
        ..., description="Structured JSON response data"
    )


class GETResponse(BaseModel):
    """Unified response model for HTTP GET requests."""

    status_code: int = Field(..., description="HTTP status code")
    content_type: str = Field(..., description="Content-Type header value")
    url: str = Field(..., description="The requested URL")
    data: HTMLResponse | APIResponse = Field(..., description="Response data based on content type")
