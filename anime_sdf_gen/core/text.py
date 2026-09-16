"""Wrapping rules shared by popup typography and headless layout tests."""

import unicodedata

NO_START = set("，。！？：；、）］｝〉》」』】〕〗〙〛…”’,.!?;:%)]}")
NO_END = set("（［｛〈《「『【〔〖〘〚“‘([{")


def cjk(value):
    return any(unicodedata.east_asian_width(ch) in ("W", "F") for ch in value)


def _clusters(value):
    result = []
    for char in value:
        if result and (unicodedata.combining(char) or char in "\ufe0e\ufe0f"):
            result[-1] += char
        else:
            result.append(char)
    return result


def _latin_wrap(value, width, measure):
    result = []
    for paragraph in value.splitlines() or [""]:
        line = ""
        for word in paragraph.split():
            if line and measure(line + " " + word) > width:
                result.append(line)
                line = ""
            while measure(word) > width and len(word) > 1:
                cut = len(word) - 1
                while cut > 1 and measure(word[:cut]) > width:
                    cut -= 1
                if line:
                    result.append(line)
                    line = ""
                result.append(word[:cut])
                word = word[cut:]
            line = (line + " " + word).strip()
        if line:
            result.append(line)
    return result


def wrap_text(value, width, measure):
    if not cjk(value):
        return _latin_wrap(value, width, measure)
    result = []
    for paragraph in value.splitlines():
        chars = _clusters(paragraph.strip())
        while chars:
            lo, hi = 1, len(chars)
            fit = 1
            while lo <= hi:
                mid = (lo + hi) // 2
                if measure("".join(chars[:mid])) <= width:
                    fit, lo = mid, mid + 1
                else:
                    hi = mid - 1
            cut = fit
            if fit < len(chars):
                for end in range(fit, 0, -1):
                    left, right = chars[end - 1], chars[end]
                    if left[-1] in NO_END or right[0] in NO_START:
                        continue
                    if left.isspace() or right.isspace() or cjk(left) or cjk(right):
                        cut = end
                        break
                else:
                    # Oversized Latin tokens still make progress. Keep attached
                    # closing punctuation with its preceding character.
                    while cut > 1 and (chars[cut][0] in NO_START or chars[cut - 1][-1] in NO_END):
                        cut -= 1
            line = "".join(chars[:cut]).strip()
            if line:
                result.append(line)
            chars = chars[cut:]
            while chars and chars[0].isspace():
                chars.pop(0)
    return result
