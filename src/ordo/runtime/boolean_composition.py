"""Shared boolean-composition parser helpers for runtime expression surfaces."""

from __future__ import annotations

from typing import Callable, TypeVar


NodeT = TypeVar("NodeT")
TokenT = TypeVar("TokenT")


def parse_boolean_or(
    *,
    parse_and: Callable[[], NodeT],
    match_keyword: Callable[[str], TokenT | None],
    make_binary: Callable[[str, NodeT, NodeT], NodeT],
) -> NodeT:
    node = parse_and()
    while match_keyword("or") is not None:
        right = parse_and()
        node = make_binary("or", node, right)
    return node


def parse_boolean_and(
    *,
    parse_not: Callable[[], NodeT],
    match_keyword: Callable[[str], TokenT | None],
    make_binary: Callable[[str, NodeT, NodeT], NodeT],
) -> NodeT:
    node = parse_not()
    while match_keyword("and") is not None:
        right = parse_not()
        node = make_binary("and", node, right)
    return node


def parse_boolean_not(
    *,
    match_not: Callable[[], TokenT | None],
    parse_not: Callable[[], NodeT],
    parse_fallback: Callable[[], NodeT],
    make_unary: Callable[[str, TokenT, NodeT], NodeT],
) -> NodeT:
    token = match_not()
    if token is not None:
        operand = parse_not()
        return make_unary("not", token, operand)
    return parse_fallback()
