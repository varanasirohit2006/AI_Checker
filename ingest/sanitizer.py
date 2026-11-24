"""Sanitization pre-scoring (AGENTS.md §6A).

Runs AFTER raw flags are persisted: strips hidden/invisible characters and maps
homoglyphs back to standard Latin — but ONLY inside mixed-script words, so
legitimate non-Latin paragraphs pass through untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

from confusable_homoglyphs import confusables

from ingest.flags import (HIDDEN_CODEPOINTS, WORD_RE, _has_latin,
                          _latin_homoglyph)


@dataclass
class SanitizeResult:
    text: str
    changes: list  # {type: removed|homoglyph, char, to?, offset, name?}

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def sanitize(text: str) -> SanitizeResult:
    changes: list[dict] = []

    kept = []
    for i, ch in enumerate(text):
        if ord(ch) in HIDDEN_CODEPOINTS:
            changes.append({"type": "removed", "char": ch,
                            "codepoint": f"U+{ord(ch):04X}",
                            "name": HIDDEN_CODEPOINTS[ord(ch)], "offset": i})
        else:
            kept.append(ch)
    stripped = "".join(kept)

    # Map confusable non-Latin letters to Latin only within mixed-script words.
    # Offsets refer to the stripped text (hidden chars already removed).
    pieces = []
    last = 0
    for m in WORD_RE.finditer(stripped):
        word = m.group()
        pieces.append(stripped[last:m.start()])
        if confusables.is_mixed_script(word) and _has_latin(word):
            mapped = []
            for j, ch in enumerate(word):
                if confusables.alias(ch) != "LATIN":
                    latin = _latin_homoglyph(ch)
                    if latin is not None:
                        changes.append({"type": "homoglyph", "char": ch, "to": latin,
                                        "codepoint": f"U+{ord(ch):04X}",
                                        "word": word, "offset": m.start() + j})
                        mapped.append(latin)
                        continue
                mapped.append(ch)
            pieces.append("".join(mapped))
        else:
            pieces.append(word)
        last = m.end()
    pieces.append(stripped[last:])

    changes.sort(key=lambda c: c["offset"])
    return SanitizeResult(text="".join(pieces), changes=changes)