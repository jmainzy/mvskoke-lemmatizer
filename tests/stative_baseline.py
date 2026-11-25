"""Reference forms from the previous lemmatizer for HFST regression tests."""

import unicodedata


def stative_stems(lemma, regular_plural):
    stem = lemma[:-1] + "ē" if lemma.endswith("e") else lemma
    initial, rest = stem[0], stem[1:]
    first = {
        "a": "vca" + rest, "ē": "vca" + rest,
        "v": "vcv" + rest, "o": "vc" + stem, "e": "cv" + rest,
    }.get(initial, "cv" + stem)
    second = {
        "a": "ecē" + rest, "ē": "ecē" + rest,
        "v": "ece" + rest, "o": "ec" + stem, "e": "ce" + rest,
    }.get(initial, "ce" + stem)
    if not regular_plural:
        return stem, first, second
    plural_first = {
        "a": "epo" + rest, "ē": "epo" + rest, "v": "epo" + rest,
        "o": "ep" + stem, "e": "pu" + rest,
    }.get(initial, "pu" + stem)
    return stem, first, second, plural_first, second[:-1] + "vkē", stem[:-1] + "vkē"


def stative_derivations(stem):
    root = stem[:-1]
    bases = {root}
    index = next((i for i in range(len(root) - 1, -1, -1) if root[i] in "ve"), None)
    if index is not None:
        grade = {"v": "a", "e": "ē"}[root[index]]
        bases.add(root[:index] + grade + root[index + 1:])
        nasal = {"v": "ą", "e": "ę̄"}[root[index]]
        bases.add(unicodedata.normalize("NFC", root[:index] + nasal + root[index + 1:]))
    return {base + ending for base in bases for ending in ("usē", "ose")}
