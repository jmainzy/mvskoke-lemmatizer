#!/usr/bin/env python3
"""Export Mvskoke LIFT headwords and continuation classes as HFST lexc."""

import argparse
from pathlib import Path
import unicodedata
import warnings
import xml.etree.ElementTree as ET


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_LIFT = PROJECT.parent / "mvskoke-dictionary" / "lexicon" / "lexicon.lift"
DEFAULT_OUTPUT = PROJECT / "grammar" / "lexicon.lexc"
POSSESSIVE_NOUNS = PROJECT / "grammar" / "possessive_nouns.tsv"
TIME_ADVERBS = PROJECT / "grammar" / "time_adverbs.tsv"

# LIFT grammatical-info values map to a lexc lexicon name and analysis tag.
PARTS_OF_SPEECH = {
    "noun": ("Nouns", "+N"),
    "verb": ("Verbs", "+V"),
    "v.": ("Verbs", "+V"),
    "adjective": ("Adjectives", "+Adj"),
    "adj": ("Adjectives", "+Adj"),
    "stative": ("Adjectives", "+Adj"),
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


def read_possessive_nouns() -> dict[str, tuple[str, str]]:
    entries = {}
    with POSSESSIVE_NOUNS.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) not in (2, 3) or fields[1] not in {"cv", "vm", "vm-bound"}:
                raise ValueError(f"{POSSESSIVE_NOUNS}:{number}: invalid noun classification")
            word = unicodedata.normalize("NFC", fields[0]).lower()
            stem = unicodedata.normalize("NFC", fields[2]).lower() if len(fields) == 3 else word
            if not word or not stem or word in entries:
                raise ValueError(f"{POSSESSIVE_NOUNS}:{number}: empty or duplicate noun")
            entries[word] = (fields[1], stem)
    return entries


def read_time_adverbs() -> dict[tuple[str, str], tuple[str, str]]:
    entries = {}
    with TIME_ADVERBS.open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if (len(fields) != 4 or fields[1] not in {"+N", "+Adv", "+Num"}
                    or fields[3] not in {"TimeRecent", "TimeRecentY", "TimeEarlier"}
                    or not fields[0] or not fields[2]):
                raise ValueError(f"{TIME_ADVERBS}:{number}: invalid time adverb")
            key = (unicodedata.normalize("NFC", fields[0]).lower(), fields[1])
            if key in entries:
                raise ValueError(f"{TIME_ADVERBS}:{number}: duplicate time adverb")
            entries[key] = (unicodedata.normalize("NFC", fields[2]).lower(), fields[3])
    return entries


def export_lexicon(lift: Path, output: Path) -> tuple[int, int]:
    if output.resolve() in (lift.resolve(), POSSESSIVE_NOUNS.resolve(), TIME_ADVERBS.resolve()):
        raise ValueError("input files and output lexc must be different files")
    headwords, skipped = read_headwords(lift)
    irregular, plurals = read_verb_relations(lift)
    possessive_classes = read_possessive_nouns()
    time_adverbs = read_time_adverbs()
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
    person_entries = []
    patient_entries = []
    comparison_entries = []
    possessive_entries = {name: [] for name in (
        "PossessiveCvNouns", "PossessiveVmNouns", "PossessiveBoundNouns",
        "PossessiveProperNouns",
    )}
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
                if tag == "+Adj":
                    continuation_classes.append("MannerAdverb")
                for continuation in continuation_classes:
                    used_classes.add(continuation)
                    lines.append(f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}{continuation}Tag ;")
                if (word.lower(), tag) in time_adverbs:
                    stem, continuation = time_adverbs[(word.lower(), tag)]
                    used_classes.add(continuation)
                    lines.append(f"{escape_lexc(word)}:{escape_lexc(stem)} {name}{continuation}Tag ;")
                if tag == "+N" and not any(char.isspace() for char in word):
                    noun_class, stem = possessive_classes.get(word.lower(), ("unknown", word.lower()))
                    destinations = {
                        "cv": ("PossessiveCvNouns",),
                        "vm": ("PossessiveVmNouns",),
                        "vm-bound": ("PossessiveBoundNouns",),
                        "unknown": ("PossessiveCvNouns", "PossessiveVmNouns"),
                    }[noun_class]
                    if word[0].isupper() and noun_class in {"vm", "unknown"}:
                        destinations += ("PossessiveProperNouns",)
                    for destination in destinations:
                        possessive_entries[destination].append(
                            f"{escape_lexc(word)}:{escape_lexc(stem)} {name}Tag ;"
                        )
                        for continuation in continuation_classes:
                            possessive_entries[destination].append(
                                f"{escape_lexc(word)}:{escape_lexc(stem)} {name}{continuation}Tag ;"
                            )
                if tag == "+Adj" and word.lower().endswith(("e", "ē")):
                    regular = word.lower() not in irregular
                    stative_forms = [
                        ("StativeBaseRegular" if regular else "StativeBaseSingular", ""),
                        ("StativeFirst", "%^SF1%^SF2%^SF3"),
                        ("StativeSecondRegular" if regular else "StativeSecondSingular",
                         "%^SS1%^SS2%^SS3"),
                    ]
                    if regular:
                        stative_forms.append(("StativeFirstPlural", "%^SP1%^SP2%^SP3"))
                    for continuation, markers in stative_forms:
                        used_classes.add(continuation)
                        lines.append(
                            f"{escape_lexc(word)}:{markers}{escape_lexc(word.lower())} "
                            f"{name}{continuation}Tag ;"
                        )
                    base_class = "StativeBaseRegular" if regular else "StativeBaseSingular"
                    used_classes.add("ComparisonAgent")
                    used_classes.add("ComparisonStative")
                    comparison_entries.extend(
                        f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}{continuation}Tag ;"
                        for continuation in (base_class, "ComparisonStative", "ComparisonAgent")
                    )
            if not is_verb_candidate(word):
                continue
            verb_class = "SingularVerb" if word.lower() in irregular else "RegularVerb"
            used_classes.add(verb_class)
            lines.append(f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}{verb_class}Tag ;")
            if tag == "+V":
                person_entries.append(f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}Tag ;")
                person_entries.append(f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}{verb_class}Tag ;")
                used_classes.add("Patient" + verb_class)
                patient_entries.append(f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}Tag ;")
                patient_entries.append(f"{escape_lexc(word)}:{escape_lexc(word.lower())} {name}Patient{verb_class}Tag ;")
            for plural in sorted(plurals.get(word.lower(), set())):
                if not is_verb_candidate(plural):
                    continue
                used_classes.add("PluralVerb")
                lines.append(f"{escape_lexc(word)}:{escape_lexc(plural)} {name}PluralVerbTag ;")
                if tag == "+V":
                    person_entries.append(f"{escape_lexc(word)}:{escape_lexc(plural)} {name}PluralVerbTag ;")
                    used_classes.add("PatientPluralVerb")
                    patient_entries.append(f"{escape_lexc(word)}:{escape_lexc(plural)} {name}PatientPluralVerbTag ;")
        lines.extend(("", f"LEXICON {name}Tag", f"{tag}: # ;"))
        for continuation in sorted(used_classes):
            lines.extend(("", f"LEXICON {name}{continuation}Tag", f"{tag}: {continuation} ;"))
    if person_entries or comparison_entries:
        lines.insert(lines.index("LEXICON Root") + 1, "PersonRoot ;")
    if ("vyetv" in headwords and ("Verbs", "+V") in headwords["vyetv"]):
        lines.insert(lines.index("LEXICON Root") + 1, "InstrumentalGo ;")
    if any(possessive_entries.values()):
        lines.insert(lines.index("LEXICON Root") + 1, "PossessiveRoot ;")
    lines.extend(("", "LEXICON PersonVerbs"))
    lines.extend(person_entries or ["0:0 # ;"])
    lines.extend(("", "LEXICON PatientVerbs"))
    lines.extend(patient_entries or ["0:0 # ;"])
    lines.extend(("", "LEXICON ComparisonAdjectives"))
    lines.extend(comparison_entries or ["0:0 # ;"])
    for name, entries in possessive_entries.items():
        lines.extend(("", f"LEXICON {name}"))
        lines.extend(entries or ["0:0 # ;"])
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
