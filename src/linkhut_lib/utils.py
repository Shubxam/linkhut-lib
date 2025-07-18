# note: make the order of the return types of functions with api calls consistent.
# i.e. all the functions which call make_get_request should use `return response.json(), response.status_code`

import json
import os
import re
import sys
from typing import Literal

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from loguru import logger

from .config import (
    LINKHUT_API_ENDPOINTS,
    LINKHUT_BASEURL,
    LINKHUT_HEADER,
    LINKPREVIEW_BASEURL,
    LINKPREVIEW_HEADER,
)
def setup_logger():
    logger.remove()
    logger.add(sys.stderr, colorize=True, level='INFO')


def get_request_headers(site: Literal["LinkHut", "LinkPreview"]) -> dict[str, str]:
    """
    Load the PAT from environment variables and return the request headers.
    """
    load_dotenv()  # Load environment variables from .env file

    if site == "LinkHut":
        pat: str | None = os.getenv("LH_PAT")
        if not pat:
            raise RequestError("LH_PAT environment variable not set")
        header: dict[str, str] = LINKHUT_HEADER
        # Create a copy of the header and format the PAT into it
        request_headers: dict[str, str] = header.copy()
        request_headers["Authorization"] = request_headers["Authorization"].format(PAT=pat)

    elif site == "LinkPreview":
        pat: str | None = os.getenv("LINK_PREVIEW_API_KEY")
        if not pat:
            raise RequestError("LINK_PREVIEW_API_KEY environment variable not set")
        header: dict[str, str] = LINKPREVIEW_HEADER
        # Create a copy of the header and format the PAT into it
        request_headers: dict[str, str] = header.copy()
        request_headers["X-Linkpreview-Api-Key"] = request_headers["X-Linkpreview-Api-Key"].format(
            API_KEY=pat
        )

    # logger.debug(f"header for {site} is {request_headers}")
    return request_headers


def make_get_request(
    url: str, header: dict[str, str], payload: dict[str, str] | None = None
) -> GETResponse:
    """
    Make a GET request to the specified URL with the provided headers.

    Args:
        url (str): The URL to make the request to.
        header (dict[str, str]): The headers to include in the request.

    Returns:
        GETResponse: The structured response object.

    Raises:
        RuntimeError: If the request fails or if the response is not JSON.
        httpx.HTTPStatusError: If the response status code indicates an error (4xx or 5xx).
        httpx.RequestError: If there is a network-related error.
        RequestError: If the content type is not supported or if an unexpected error occurs.
    """
    try:
        logger.debug(f"making get request to following url: {url}")
        response = httpx.get(url=url, headers=header, params=payload, timeout=30.0)
        logger.debug(
            f"response is {json.dumps(response.json(), indent=2)} with status code {response.status_code}"
        )
        status_code: int = response.status_code
        request_url: str = response.url.__str__()
        content_type_str: str = response.headers.get("content-type", "")
        if "application/json" in content_type_str:
            content_type = "application/json"
            data = APIResponse(content=response.json())
        elif "text/html" in content_type_str:
            content_type = "text/html"
            data = HTMLResponse(content=BeautifulSoup(response.text, "html.parser"))
        else:
            raise RequestError(
                f"Unsupported content type: {content_type_str}. Expected 'application/json' or 'text/html'."
            )
        response_object: GETResponse = GETResponse(
            status_code=status_code,
            content_type=content_type,
            url=request_url,
            data=data,
        )
        return response_object

    except httpx.HTTPStatusError as exc:
        raise RequestError(
            f"HTTP error occurred: {exc.response.text}",
            status_code=exc.response.status_code,
            response_data=exc.response.json()
            if exc.response.headers.get("content-type", "").startswith("application/json")
            else None,
        ) from exc
    except httpx.RequestError as exc:
        raise RequestError(
            f"Network error occurred while requesting {exc.request.url!r}: {exc}"
        ) from exc
    except Exception as e:
        raise RequestError(f"An unexpected error occurred: {e}") from e


def linkhut_api_call(action: str, payload: dict[str, str]) -> httpx.Response:
    """
    Make an API call to the specified LinkHut endpoint and return the response.

    Args:
        action (str): The API action to perform (e.g., "bookmark_create")
        payload (dict[str, str], optional): Query parameters for the request

    Returns:
        Response: The response object from the API
    """
    # Note: Different API endpoints return different data, let the calling function handle the extraction and exception handling.
    # calling functions will define how to handle the exception and the replacement values to use if http request fails.
    url: str = LINKHUT_BASEURL + LINKHUT_API_ENDPOINTS[action]

    # Add query parameters if provided
    if payload:
        url += "?"
        params: list[str] = []
        for key, value in payload.items():
            params.append(f"{key}={value}")
        url += "&".join(params)

    header: dict[str, str] = get_request_headers(site="LinkHut")
    logger.debug(f"making request to {url} with header {header}")
    response: httpx.Response = make_get_request(url=url, header=header)
    return response


def get_link_title(dest_url: str) -> str:
    """
    Fetch the title of a link using the LinkPreview API.
    Args:
        dest_url (str): The URL of the link to fetch the title for.

    Returns:
        - str: The title of the link.

    Note: returns url as title if the request fails.
    """
    # verify_url(dest_url)
    title: str
    dest_url_str: str = f"q={dest_url}"

    # fetch the following fields: title, description, url (disabling, as setting custom fields is supported but does not work with the API)
    # fields_str = "fields=title,description,url"

    # allow websites with blocked content
    block_content: str = "block_content=false"

    api_endpoint: str = f"/?{block_content}&{dest_url_str}"
    request_url: str = LINKPREVIEW_BASEURL + api_endpoint

    logger.debug(f"making request to get title : {request_url}")

    header: dict[str, str] = get_request_headers("LinkPreview")

    try:
        response: httpx.Response = make_get_request(url=request_url, header=header)
        title_str: str = response.json().get("title", "")
        title = title_str if title_str else dest_url
    except Exception as e:
        logger.error(f"Error fetching the title for {dest_url}: {e}")
        title = dest_url

    # function is supposed to send link title, so we send link title by handling the exceptions here.
    return title


def get_tags_suggestion(dest_url: str) -> str:
    """
    Fetch tags suggestion for a link using the LinkHut API.
    Args:
        dest_url (str): The URL of the link to fetch tags for.

    Returns:
        str: A str of suggested tags separated by comma.

    Note: returns "AutoTagFetchFailed" if the request fails or no suggested tags found.
    """
    action: str = "tag_suggest"
    payload: dict[str, str] = {
        "url": dest_url,
    }

    logger.debug(f"fetching suggested tags for : {dest_url}")

    try:
        response: httpx.Response = linkhut_api_call(action=action, payload=payload)
        # above call will always return a response (200) except in case of network error or API down.
        # if no tags are found, it will return an empty dict.

        status_code: int = response.status_code
        response_dict: list[dict[str, list[str]]] = response.json()

        if status_code == 200:
            tag_list: list[str] = response_dict[0]["popular"] + response_dict[1]["recommended"]
            if len(tag_list) > 0:
                return ",".join(tag_list)
            else:
                logger.warning(f"No auto tag suggestions found for: {dest_url}")
                return "AutoTagFetchFailed"
        else:
            logger.warning("Issue with the API. Auto Tag Fetch Failed.")
            return "AutoTagFetchFailed"

    except Exception as e:
        # if there is a network error or the API is down, we handle that in the following exception.
        logger.error(f"Error fetching tags for {dest_url}: {e}")
        return "AutoTagFetchFailed"


def encode_url(url: str) -> str:
    """
    Encode the URL for use in API calls.
    Args:
        url (str): The URL to encode.

    Returns:
        str: The encoded URL.
    """
    return (
        url.replace(":", "%3A")
        .replace("/", "%2F")
        .replace("?", "%3F")
        .replace("&", "%26")
        .replace("=", "%3D")
        .replace("\\", "%5C")
    )


def tags_in_api_format(tags: list[Tag]) -> str:
        """Return tags in string format separated by +"""
        return "+".join(tag.name for tag in tags)


# def verify_url(url: str) -> bool:
#     """
#     Verify if the URL is valid.
#     Args:
#         url (str): The URL to verify.

#     Returns:
#         bool: True if the URL is valid, False otherwise.

#     Raises:
#         InvalidURLError: If the URL format is invalid.
#     """
#     # todo: make url validation better, also check for pattern *://*.*
#     if not url.startswith(("http://", "https://")):
#         raise InvalidURLError("URL must start with http:// or https://")
#     elif len(url) > 2048:
#         raise InvalidURLError("URL length exceeds 2048 characters")

#     return True


# def is_valid_date(date_str: str) -> bool:
#     """
#     Check if the given string is a valid date in YYYY-MM-DD format.

#     Args:
#         date_str (str): The date string to validate.

#     Returns:
#         bool: True if the date is valid, False otherwise.

#     Raises:
#         InvalidDateFormatError: If the date format is invalid.
#     """
#     date_pattern = r"^\d{4}-\d{2}-\d{2}$"
#     result = bool(re.match(date_pattern, date_str))
#     if not result:
#         raise InvalidDateFormatError(
#             f"Invalid date format: {date_str}. Expected format is YYYY-MM-DD."
#         )
#     return result


# def is_valid_tag(tag: str) -> bool:
#     """
#     Check if the given string is a valid tag.

#     Args:
#         tag (str): The tag string to validate.

#     Returns:
#         bool: True if the tag is valid, False otherwise.

#     Raises:
#         InvalidTagFormatError: If the tag format is invalid.
#     """
#     if not tag:
#         raise InvalidTagFormatError("Tag cannot be empty")
#     if len(tag) > 50:
#         raise InvalidTagFormatError(f"Tag '{tag}' exceeds maximum length of 50 characters")
#     if not all(c.isalnum() or c in "-_" for c in tag):
#         raise InvalidTagFormatError(
#             f"Tag '{tag}' contains invalid characters. Only alphanumeric, hyphen, and underscore are allowed"
#         )
#     return True


if __name__ == "__main__":
    # Example usage
    dest_url = "http://news.ycombinator.com"
    # dest_url_base = dest_url.split("?")[0]

    # print(f"Title info: {get_link_title(dest_url)}")
    # print(f"Tags suggestion: {get_tags_suggestion(dest_url_base)}")
    # print(f"verify url: {verify_url(dest_url)}")
    print(encode_url("\n Now I've read this"))
