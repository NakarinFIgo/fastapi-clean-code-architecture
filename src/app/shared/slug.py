import re

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def to_crud_slug(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower().replace("_", "-")
