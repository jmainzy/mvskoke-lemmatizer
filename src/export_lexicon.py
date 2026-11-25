#!/usr/bin/env python3
"""Export Mvskoke LIFT headwords and continuation classes as HFST lexc."""

import argparse
from pathlib import Path
import unicodedata
import warnings
import xml.etree.ElementTree as ET


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_LIFT = PROJECT.parent / "mvskoke-dictionary" / "lexicon" / "lexicon.lift"
DEFAULT_OUTPUT = PROJECT / "src" / "lexicon.lexc"

# LIFT grammatical-info values map to a lexc lexicon name and analysis tag.
PARTS_OF_SPEECH = {
    "noun": ("Nouns", "+N"),
    "verb": ("Verbs", "+V"),
    "v.": ("Verbs", "+V"),
    "adjective": ("Adjectives", "+Adj"),
    "adverb": ("Adverbs", "+Adv"),
    "numeral": ("Numerals", "+Num"),
    "interjection": ("Interjections", "+Interj"),
    "participle": ("Participles", "+Part"),
    "pronoun": ("Pronouns", "+Pron"),
    "adjectival noun": ("AdjectivalNouns", "+AdjN"),
    "postposition": ("Postpositions", "+Post"),
    "connective": ("Connectives", "+Conn"),
    "auxiliary verb": ("AuxiliaryVerbs", "+AuxV"),
    "demonstrative": ("Demonstratives", "+Dem"),
    "suffix": ("Suffixes", "+Suff"),
    "prefix": ("Prefixes", "+Pref"),
}
UNKNOWN_POS = ("Uncategorized", "+Unknown")


def escape_lexc(text: str) -> str:
    """Escape characters that have special meaning in lexc string entries."""
    if any(unicodedata.category(char) == "Cc" for char in text):
        raise ValueError(f"headword contains a control character: {text!r}")
    return "".join("%" + char if char in ' %!;:"<>0#' else char for char in text)


def read_headwords(lift: Path) -> tuple[dict[str, set[tuple[str, str]]], int]:
    headwords: dict[str, set[tuple[str, str]]] = {}
    skipped = 0
    for _, entry in ET.iterparse(lift, events=("end",)):
        if entry.tag != "entry":
            continue
        text = entry.find("./lexical-unit/form[@lang='mus']/text")
        word = "".join(text.itertext()).strip() if text is not None else ""
        if word:
            word = unicodedata.normalize("NFC", word)
            escape_lexc(word)
            categories = headwords.setdefault(word, set())
            senses = entry.findall(".//sense")
            if not senses:
                categories.add(UNKNOWN_POS)
            for sense in senses:
                info = sense.find("./grammatical-info")
                value = (info.get("value") or "").strip().lower() if info is not None else ""
                if not value:
                    categories.add(UNKNOWN_POS)
                elif value in PARTS_OF_SPEECH:
                    categories.add(PARTS_OF_SPEECH[value])
                else:
                    raise ValueError(f"{lift}: unknown part of speech {value!r} for {word!r}")
        else:
            skipped += 1
        entry.clear()
    if not headwords:
        raise ValueError(f"{lift}: no Mvskoke headwords found")
    return headwords, skipped


def read_verb_relations(lift: Path) -> tuple[set[str], dict[str, set[str]]]:
    words_by_id: dict[str, str] = {}
    irregular: set[str] = set()
    references: dict[str, set[str]] = {}
    for _, entry in ET.iterparse(lift, events=("end",)):
        if entry.tag != "entry":
            continue
        text = entry.find("./lexical-unit/form[@lang='mus']/text")
        word = unicodedata.normalize("NFC", "".join(text.itertext()).strip()) if text is not None else ""
        entry_id = entry.get("id")
        if word and entry_id:
            words_by_id[unicodedata.normalize("NFC", entry_id)] = word
        if word:
            for relation in entry.findall("./relation"):
                kind = relation.get("type")
                if kind in {"EntryPl", "EntryDu", "EntryTpl"}:
                    irregular.add(word.lower())
                reference = relation.get("ref")
                if kind in {"EntryDu", "EntryTpl"}:
                    if reference:
                        references.setdefault(word.lower(), set()).add(unicodedata.normalize("NFC", reference))
                    else:
                        warnings.warn(f"{lift}: {kind} relation for {word!r} has no reference", stacklevel=2)
        entry.clear()
    plurals: dict[str, set[str]] = {}
    for word, refs in references.items():
        for ref in refs:
            if ref not in words_by_id:
                warnings.warn(f"{lift}: plural relation for {word!r} references missing entry {ref!r}", stacklevel=2)
            else:
                plurals.setdefault(word, set()).add(words_by_id[ref].lower())
    return irregular, plurals


def is_segmentable(word: str) -> bool:
    word = word.lower()
    phrase = word.startswith("etem ") and not any(char.isspace() for char in word[5:])
    return (phrase and word.endswith("etv")) or not any(char.isspace() for char in word)


def is_verb_candidate(word: str) -> bool:
    word = word.lower()
    return (
        word.endswith("etv") and word != "ometv" and len(word) > 4
        and is_segmentable(word)
        and any(char in "aeēiouv" for char in word[:-3].rsplit(" ", 1)[-1])
    )


def export_lexicon(lift: Path, output: Path) -> tuple[int, int]:
    if lift.resolve() == output.resolve():
        raise ValueError("input LIFT and output lexc must be different files")
    headwords, skipped = read_headwords(lift)
    irregular, plurals = read_verb_relations(lift)
    lexicons: dict[tuple[str, str], list[str]] = {}
    for word, categories in sorted(headwords.items()):
        for category in categories:
            lexicons.setdefault(category, []).append(word)
    lines = [
        "! Generated from LIFT Mvskoke headwords; do not edit by hand.",
        "Multichar_Symbols",
        " ".join(tag for _, tag in sorted(lexicons)),
        "",
        "LEXICON Root",
    ]
    lines.extend(f"{name} ;" for name, _ in sorted(lexicons))
    for (name, tag), words in sorted(lexicons.items()):
        lines.extend(("", f"LEXICON {name}"))
        lines.extend(f"{escape_lexc(word)} {name}Tag ;" for word in words)
        used_classes = set()
        for word in words:
            if is_segmentable(word):
                continuation_classes = ["Nominal"]
                if word.lower().endswith(("e", "ē")):
                    continuation_classes.append("DefiniteVowel")
                    tags_for_word = {pos for _, pos in headwords[word]}
                    if "+Adj" in tags_for_word or not (tags_for_word - {"+Unknown"}):
                        continuation_classes.append("StativePast")
                elif word.lower().endswith("etv"):
                    continuation_classes.append("DefiniteVerb")
                if tag == "+Num" and word.lower().endswith("en"):
                    continuation_classes.append("NumeralBase")
                for continuation in continuation_classes:
                    used_classes.add(continuation)
                    lines.append(f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}{continuation}Tag ;")
            if not is_verb_candidate(word):
                continue
            verb_class = "SingularVerb" if word.lower() in irregular else "RegularVerb"
            used_classes.add(verb_class)
            lines.append(f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}{verb_class}Tag ;")
            for plural in sorted(plurals.get(word.lower(), set())):
                if not is_verb_candidate(plural):
                    continue
                used_classes.add("PluralVerb")
                lines.append(f"{escape_lexc(word)}:{escape_lexc(plural)} {name}PluralVerbTag ;")
        lines.extend(("", f"LEXICON {name}Tag", f"{tag}: # ;"))
        for continuation in sorted(used_classes):
            lines.extend(("", f"LEXICON {name}{continuation}Tag", f"{tag}: {continuation} ;"))
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(headwords), skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lift", type=Path, default=DEFAULT_LIFT, help="input LIFT dictionary")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="output lexc file")
    args = parser.parse_args()
    try:
        count, skipped = export_lexicon(args.lift, args.output)
    except (OSError, ET.ParseError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(f"Exported {count} distinct headwords to {args.output}; skipped {skipped} entries without a Mvskoke headword.")


if __name__ == "__main__":
    main()
