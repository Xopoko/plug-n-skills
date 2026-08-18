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
SEGMENT_SAFE_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


class GitHubRequestError(ValueError):
    """The requested URL is not an allowlisted HTTPS GitHub endpoint."""


class _AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects that would send credentials off GitHub."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        assert_allowlisted_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def assert_allowlisted_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if parsed.scheme != "https" or not host or host.casefold() not in ALLOWED_HOSTS:
        raise GitHubRequestError(f"not an allowlisted HTTPS GitHub endpoint: {url}")
    if parsed.username or parsed.password:
        raise GitHubRequestError("GitHub URLs must not embed credentials")


def validate_path_segment(value: str, label: str) -> str:
    """Reject segments that could alter the request path or become a git option."""

    if not value:
        raise GitHubRequestError(f"{label} must not be empty")
    if value.startswith("-"):
        raise GitHubRequestError(f"{label} must not start with '-'")
    if not set(value) <= SEGMENT_SAFE_CHARACTERS:
        raise GitHubRequestError(f"{label} contains unsupported characters: {value}")
    if value in (".", ".."):
        raise GitHubRequestError(f"{label} must not be a relative path segment")
    return value


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
    segments = [segment for segment in value.strip("/").split("/") if segment]
    if not segments:
        raise GitHubRequestError(f"{label} must not be empty")
    for segment in segments:
        validate_path_segment(segment, label)
    return "/".join(urllib.parse.quote(segment, safe="") for segment in segments)


def github_api_contents_url(repo: str, path: str, ref: str) -> str:
    quoted_repo = _quote_relative_path(repo, "repo")
    quoted_path = _quote_relative_path(path, "path")
    query = urllib.parse.urlencode({"ref": ref})
    return f"https://api.github.com/repos/{quoted_repo}/contents/{quoted_path}?{query}"
