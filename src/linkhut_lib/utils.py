# note: make the order of the return types of functions with api calls consistent.
# i.e. all the functions which call make_get_request should use `return response.json(), response.status_code`

import os
import sys
from typing import Literal

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from loguru import logger

from .config import (
    LH_API_ENDPOINT,
    LINKHUT_BASEURL,
    LINKHUT_HEADER,
    LINKPREVIEW_HEADER,
    firefox_user_agent,
)
from .exceptions import RequestError
from .models import APIResponse, GETResponse, HTMLResponse, Tag


def setup_logger():
    logger.remove()
    logger.add(sys.stderr, colorize=True, level='INFO')


def get_request_headers(site: Literal['LinkHut', 'LinkPreview']) -> dict[str, str]:
    """
    Load the PAT from environment variables and return the request headers.
    """
    load_dotenv()  # Load environment variables from .env file

    if site == 'LinkHut':
        pat: str | None = os.getenv('LH_PAT')
        if not pat:
            raise RequestError('LH_PAT environment variable not set')
        header: dict[str, str] = LINKHUT_HEADER
        # Create a copy of the header and format the PAT into it
        request_headers: dict[str, str] = header.copy()
        request_headers['Authorization'] = request_headers['Authorization'].format(
            PAT=pat
        )

    elif site == 'LinkPreview':
        pat: str | None = os.getenv('LINK_PREVIEW_API_KEY')
        if not pat:
            raise RequestError('LINK_PREVIEW_API_KEY environment variable not set')
        header: dict[str, str] = LINKPREVIEW_HEADER
        # Create a copy of the header and format the PAT into it
        request_headers: dict[str, str] = header.copy()
        request_headers['X-Linkpreview-Api-Key'] = request_headers[
            'X-Linkpreview-Api-Key'
        ].format(API_KEY=pat)

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
        RequestError: If
          - the HTTP GET Response has unknown content-type [not application/json or text/html]
          - HTTP response has status code 4xx or 5xx
          - there is a network-related error
          - an unexpected error occurs during the request.
    """
    try:
        logger.debug(f'making get request to following url: {url}')
        if payload is None:
            payload = {}
        response = httpx.get(url=url, headers=header, params=payload, timeout=10.0)
        status_code: int = response.status_code
        request_url: str = response.url.__str__()
        content_type_str: str = response.headers.get('content-type', '')
        if 'application/json' in content_type_str:
            content_type = 'application/json'
            data = APIResponse(content_json=response.json())
        elif 'text/html' in content_type_str:
            content_type = 'text/html'
            data = HTMLResponse(
                content_soup=BeautifulSoup(response.text, 'html.parser')
            )
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
            f'HTTP error occurred: {exc.response.text}',
            status_code=exc.response.status_code,
            response_data=exc.response.json()
            if exc.response.headers.get('content-type', '').startswith(
                'application/json'
            )
            else None,
        ) from exc
    except httpx.RequestError as exc:
        raise RequestError(
            f'Network error occurred while requesting {exc.request.url!r}: {exc}'
        ) from exc
    except Exception as e:
        raise RequestError(f'An unexpected error occurred: {e}') from e


def linkhut_api_call(action: LH_API_ENDPOINT, payload: dict[str, str]) -> APIResponse:
    """
    Make an API call to the specified LinkHut endpoint and return the response.

    Args:
        action (str): The API action to perform (e.g., "bookmark_create")
        payload (dict[str, str], optional): Query parameters for the request

    Returns:
        Response: The response object containing the API response data.
    Raises:
        RequestError: If
          - the HTTP GET Response has unknown content-type [not application/json or text/html]
          - HTTP response has status code 4xx or 5xx
          - there is a network-related error
          - an unexpected error occurs during the request.

    """
    # Note: Different API endpoints return different data, let the calling function handle the extraction and exception handling.
    # calling functions will define how to handle the exception and the replacement values to use if http request fails.
    url: str = LINKHUT_BASEURL + action.value

    header: dict[str, str] = get_request_headers(site='LinkHut')
    logger.debug(f'making request to {url} with header {header}')
    response: GETResponse = make_get_request(url=url, header=header, payload=payload)
    if not isinstance(response.data, APIResponse):
        raise RequestError(f'Expected APIResponse but got {type(response.data)}')
    return response.data


def get_link_meta(dest_url: str) -> tuple[str, str]:
    """
    Fetch the url metadata.
    Args:
        dest_url (str): The URL to fetch the title for.

    Returns:
        - str: The title of the link.
        - description: The description of the link.


    Note: If title fetching fails due to network errors or access restrictions,
      returns the URL as the title.
    """

    logger.debug(f'making request to get title : {dest_url}')

    try:
        header: dict[str, str] = {
            'User-Agent': firefox_user_agent,
        }
        response: GETResponse = make_get_request(url=dest_url, header=header)
        if not isinstance(response.data, HTMLResponse):
            logger.error(
                f'Expected HTMLResponse but got {type(response.data)} for URL: {dest_url}'
            )
            return dest_url, ''

        # Extract the title from the HTML content
        soup: BeautifulSoup = response.data.content_soup  # type: ignore[attr-defined]

        # use the open graph title and description if available
        og_title_tag = soup.find('meta', property='og:title')
        open_graph_title: str = (
            str(og_title_tag.get('content', '')) if og_title_tag is not None else ''
        )
        og_desc_tag = soup.find('meta', property='og:description')
        open_graph_description: str = (
            str(og_desc_tag.get('content', '')) if og_desc_tag is not None else ''
        )

        # Fallback to the HTML title if Open Graph title is not available
        title_tag = soup.find('title')
        html_title: str = title_tag.text.strip() if title_tag is not None else ''

        title: str = open_graph_title or html_title or dest_url
        desc: str = open_graph_description or ''

        # function is supposed to send link title, so we send link title by handling the exceptions here.
        return title, desc
    except httpx.RequestError as e:
        logger.warning(f'Network error while fetching title for {dest_url}: {e}')
        return dest_url, ''
    except Exception as e:
        logger.error(f'An error occurred while fetching title for {dest_url}: {e}')
        return dest_url, ''


def get_tags_suggestion(dest_url: str) -> list[Tag] | list[None]:
    """
    Fetch tags suggestion for a link using the LinkHut API.
    Args:
        dest_url (str): The URL of the link to fetch tags for.

    Returns:
        str: A str of suggested tags separated by comma.

    Note: returns "AutoTagFetchFailed" if the request fails or no suggested tags found.
    """
    action: LH_API_ENDPOINT = LH_API_ENDPOINT.TAG_SUGGEST
    payload: dict[str, str] = {
        'url': dest_url,
    }

    logger.debug(f'fetching suggested tags for : {dest_url}')

    try:
        response: GETResponse = linkhut_api_call(action=action, payload=payload)
        tags: list[Tag] | list[None] = []
        tag_suggestions: list[dict[str, list[str]]] = response.data.content
        if tag_suggestions[0]['popular']:
            tags.extend([Tag(name=tag) for tag in tag_suggestions[0]['popular']])
        if tag_suggestions[1]['recommended']:
            tags.extend([Tag(name=tag) for tag in tag_suggestions[1]['recommended']])
        if not tags:
            return []
        return tags
    except RequestError as e:
        # if there is a network error or the API is down, we handle that in the following exception.
        logger.warning(f'Failed to fetch tags for {dest_url}: {e}')
        return []


def encode_url(url: str) -> str:
    """
    Encode the URL for use in API calls.
    Args:
        url (str): The URL to encode.

    Returns:
        str: The encoded URL.
    """
    return (
        url.replace(':', '%3A')
        .replace('/', '%2F')
        .replace('?', '%3F')
        .replace('&', '%26')
        .replace('=', '%3D')
        .replace('\\', '%5C')
    )


def tags_in_api_format(tags: list[Tag]) -> str:
    """Return tags in string format separated by +"""
    return '+'.join(tag.name for tag in tags)
