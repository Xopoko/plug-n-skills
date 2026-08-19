#!/usr/bin/env python3
"""Shared GitHub helpers for skill install scripts."""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
from typing import Any

ALLOWED_HOSTS = frozenset(
    {
        "api.github.com",
        "codeload.github.com",
        "github.com",
        "objects.githubusercontent.com",
        "raw.githubusercontent.com",
    }
)
REQUEST_TIMEOUT_SECONDS = 30
REPOSITORY_COMPONENT_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
INVALID_REF_CHARACTERS = frozenset(" ~^:?*[\\;")


class GitHubRequestError(ValueError):
    """The requested URL is not an allowlisted HTTPS GitHub endpoint."""


def _allowlisted_https_origin(url: str) -> tuple[str, str, int]:
    """Return a normalized origin after enforcing the GitHub URL policy."""

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if parsed.username or parsed.password:
        raise GitHubRequestError("GitHub URLs must not embed credentials")
    if parsed.scheme.casefold() != "https" or not host:
        raise GitHubRequestError("not an allowlisted HTTPS GitHub endpoint")
    normalized_host = host.casefold()
    if normalized_host not in ALLOWED_HOSTS:
        raise GitHubRequestError("not an allowlisted HTTPS GitHub endpoint")
    try:
        port = parsed.port
    except ValueError as exc:
        raise GitHubRequestError("GitHub URL has an invalid port") from exc
    if port not in (None, 443):
        raise GitHubRequestError("GitHub URLs must use the default HTTPS port")
    return ("https", normalized_host, 443)


class _AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block off-GitHub redirects and strip credentials across GitHub origins."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        target_origin = _allowlisted_https_origin(newurl)
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if (
            redirected is not None
            and _allowlisted_https_origin(req.full_url) != target_origin
        ):
            redirected.remove_header("Authorization")
        return redirected


def assert_allowlisted_url(url: str) -> None:
    _allowlisted_https_origin(url)


def validate_repository_component(value: str, label: str) -> str:
    """Validate a GitHub owner or repository name used inside a URL path."""

    if not value:
        raise GitHubRequestError(f"{label} must not be empty")
    if not set(value) <= REPOSITORY_COMPONENT_CHARACTERS:
        raise GitHubRequestError(f"{label} contains unsupported characters: {value}")
    if value in (".", ".."):
        raise GitHubRequestError(f"{label} must not be a relative path segment")
    return value


def validate_git_ref(value: str, label: str = "ref") -> str:
    """Accept ordinary Git refs, including slash refs, without option injection."""

    if not value:
        raise GitHubRequestError(f"{label} must not be empty")
    if value.startswith("-"):
        raise GitHubRequestError(f"{label} must not start with '-'")
    if value.startswith("/") or value.endswith("/") or "//" in value:
        raise GitHubRequestError(f"{label} must be a relative Git ref")
    if value == "@" or ".." in value or "@{" in value:
        raise GitHubRequestError(f"{label} is not a valid Git ref")
    if any(
        character in INVALID_REF_CHARACTERS
        or ord(character) < 32
        or ord(character) == 127
        for character in value
    ):
        raise GitHubRequestError(f"{label} is not a valid Git ref")
    components = value.split("/")
    if any(
        component in (".", "..")
        or component.endswith(".")
        or component.casefold().endswith(".lock")
        for component in components
    ):
        raise GitHubRequestError(f"{label} is not a valid Git ref")
    return value


def validate_relative_repo_path(value: str, label: str) -> list[str]:
    """Return safe POSIX repo-path components while preserving their text."""

    if not value:
        raise GitHubRequestError(f"{label} must not be empty")
    if value.startswith(("/", "\\")) or "\\" in value:
        raise GitHubRequestError(f"{label} must be a relative repository path")
    if value.startswith(("-", ":")):
        raise GitHubRequestError(
            f"{label} must not start with an option or pathspec marker"
        )
    components = value.split("/")
    if any(not component for component in components):
        raise GitHubRequestError(f"{label} must use non-empty path components")
    if ":" in components[0]:
        raise GitHubRequestError(f"{label} must not contain a drive prefix")
    if any(component in (".", "..") for component in components):
        raise GitHubRequestError(f"{label} must not contain relative path components")
    if any(
        ord(character) < 32 or ord(character) == 127
        for component in components
        for character in component
    ):
        raise GitHubRequestError(f"{label} contains control characters")
    return components


def github_request(url: str, user_agent: str) -> bytes:
    assert_allowlisted_url(url)
    headers = {"User-Agent": user_agent}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    opener = urllib.request.build_opener(_AllowlistedRedirectHandler())
    with opener.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
        return resp.read()


def _quote_relative_path(value: str, label: str) -> str:
    components = validate_relative_repo_path(value, label)
    return "/".join(
        urllib.parse.quote(component, safe="") for component in components
    )


def _quote_repository(repo: str) -> str:
    components = repo.split("/")
    if len(components) != 2:
        raise GitHubRequestError("repo must be in owner/repo format")
    owner = validate_repository_component(components[0], "repository owner")
    name = validate_repository_component(components[1], "repository name")
    return "/".join(
        urllib.parse.quote(component, safe="") for component in (owner, name)
    )


def github_api_contents_url(repo: str, path: str, ref: str) -> str:
    quoted_repo = _quote_repository(repo)
    quoted_path = _quote_relative_path(path, "path")
    query = urllib.parse.urlencode({"ref": validate_git_ref(ref)})
    return f"https://api.github.com/repos/{quoted_repo}/contents/{quoted_path}?{query}"
