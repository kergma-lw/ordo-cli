"""JSON-shaped value aliases used by the public model layer."""

from __future__ import annotations

from typing import TypeAlias


class AuthoredString(str):
    """String value that preserves authored YAML scalar style."""

    __slots__ = ("style",)

    def __new__(cls, value: str, *, style: str = "plain") -> "AuthoredString":
        instance = super().__new__(cls, value)
        instance.style = style
        return instance


def authored_string_style(value: object) -> str | None:
    """Return preserved authored style for one string-like value when available."""

    if isinstance(value, AuthoredString):
        return value.style
    return None


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]
JSONArray: TypeAlias = list[JSONValue]
