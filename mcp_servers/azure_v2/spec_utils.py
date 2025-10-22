import re
from typing import Any


def _fix_hyphens_in_charclass(class_text: str) -> str:
    """
    Given the inside of a [...] character class, escape '-' when it's not a
    proper range hyphen (i.e., not between two unescaped alphanumeric literals).
    """
    out = []
    i = 0
    n = len(class_text)

    while i < n:
        ch = class_text[i]

        # Preserve escaped sequences like \d, \w, \-, etc.
        if ch == "\\" and i + 1 < n:
            out.append(ch)
            out.append(class_text[i + 1])
            i += 2
            continue

        if ch == "-":
            # Look at previous effective (unescaped) char
            k = i - 1
            prev_eff = None
            if k >= 0:
                if class_text[k] != "\\":
                    prev_eff = class_text[k]

            # Look at next effective (unescaped) char
            k = i + 1
            next_eff = None
            if k < n:
                if class_text[k] != "\\":
                    next_eff = class_text[k]

            # Keep hyphen unescaped only if it's clearly a range like A-Z or 0-9
            if prev_eff and next_eff and prev_eff.isalnum() and next_eff.isalnum():
                out.append("-")
            else:
                out.append("\\-")
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _fix_one_regex_pattern(pattern: str) -> str:
    """
    Fixes invalid hyphen placements inside character classes for a whole regex pattern.
    """
    if not isinstance(pattern, str) or "[" not in pattern or "-" not in pattern:
        return pattern

    # Replace each [...] block using the helper above.
    def repl(m: re.Match) -> str:
        inside = m.group(0)[1:-1]  # drop the surrounding brackets
        fixed_inside = _fix_hyphens_in_charclass(inside)
        return f"[{fixed_inside}]"

    return re.sub(r"\[(?:\\.|[^\]])+\]", repl, pattern)


def is_valid_regex(pattern: str) -> bool:
    """
    Return True iff `pattern` is a syntactically valid Python regular expression.
    """
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False


def fix_regex_patterns(obj: Any, key_name: str = "pattern") -> int:
    """fix invalid regex patterns"""

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key_name:
                if isinstance(v, str):
                    if not is_valid_regex(v):
                        obj[k] = _fix_one_regex_pattern(v)
            else:
                fix_regex_patterns(v, key_name)

    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            fix_regex_patterns(item, key_name)


def remove_exclusive_minmax_ensure_prop(obj):
    """Recursively:
    1) remove 'exclusiveMinimum/Maximum' when value is a bool
    2) add empty 'properties' if type == 'object' and missing
    """
    if isinstance(obj, dict):
        # 1) drop boolean exclusive* keys
        for k in ("exclusiveMinimum", "exclusiveMaximum"):
            if isinstance(obj.get(k), bool):
                obj.pop(k, None)

        # 2) ensure properties for object types
        if obj.get("type") == "object" and "properties" not in obj:
            obj["properties"] = {}

        # recurse into children
        for key, val in list(obj.items()):
            obj[key] = remove_exclusive_minmax_ensure_prop(val)
        return obj

    if isinstance(obj, list):
        for i, v in enumerate(obj):
            obj[i] = remove_exclusive_minmax_ensure_prop(v)
        return obj

    return obj
