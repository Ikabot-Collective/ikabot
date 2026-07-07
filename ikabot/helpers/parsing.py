#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""Helpers for extracting data from Ikariam responses. When Gameforge serves
an unexpected page (error page, maintenance, layout change), a plain
re.search(...).group() dies with "'NoneType' object has no attribute 'group'"
— these helpers raise a ParseError that says what was being looked for
instead, so logs and Telegram reports become actionable."""

import re

# how much of the unparseable response to include in the error message
_SNIPPET_LENGTH = 300


class ParseError(Exception):
    """Raised when an expected pattern is not found in an Ikariam response"""


def search_or_raise(pattern, text, what, flags=0):
    """Like re.search, but raises a descriptive ParseError instead of
    returning None when the pattern is not found.

    Parameters
    ----------
    pattern : str
        regular expression to search for
    text : str
        response text to search in
    what : str
        human-readable description of what is being extracted,
        e.g. "city data" — used in the error message
    flags : int
        optional re flags

    Returns
    -------
    match : re.Match
    """
    match = re.search(pattern, text, flags)
    if match is None:
        snippet = str(text)[:_SNIPPET_LENGTH].replace("\n", " ")
        raise ParseError(
            "Could not find {} in the response from Ikariam. The page may be an "
            "error page or the game layout changed. Response starts with: {}".format(
                what, snippet
            )
        )
    return match
