#!/usr/bin/env python3
"""Compile a modest Mvskoke morphological FST from a LIFT dictionary."""

import argparse
from collections import deque
from copy import copy
import json
from pathlib import Path
from typing import Callable, cast
import unicodedata
import warnings
import xml.etree.ElementTree as ET

from pyfoma import FST, algorithms


DEFAULT_LEXICON = Path(__file__).resolve().parent.parent / "mvskoke-dictionary" / "lexicon" / "lexicon.lift"
VOWELS = "aeēiouv"
CONSONANTS = "cfhklmnprstwy"
POSSESSIVE_PREFIXES = ("en", "pum", "cem", "pom", "cen", "vm", "vn", "vc", "cv", "ec")
VOWEL_ALTERNATES = {"a": "v", "v": "a", "o": "u", "u": "o"}
FUZZY_ALTERNATES = {**VOWEL_ALTERNATES, "f": "h"}
PRESENT_ENDINGS = (
    "is", "etskes", "eckes", "ecces", "etces", "etses", "es",
    "ēs", "atskes", "ackes", "atses", "akes",
)
FUTURE_ENDINGS = ("arēs", "etskvrēs", "vrēs", "ēyvrēs", "atskvrēs", "vkvrēs")
IMPERATIVE_ENDINGS = ("vs", "vks", "epvs", "ekot", "vkēs", "vkēts", "ekvs", "vccvs", "vkvccvs")
VHAN_ENDINGS = (
    "vhanis", "vhanetskes", "vhaneckes", "vhanecces", "vhanetces",
    "vhanetses", "vhanes", "vhanēs", "vhanatskes", "vhanackes",
    "vhanatses", "vkvhanes",
)
AUXILIARY_ENDINGS = (
    "iyēt", "etsket", "ecket", "eccet", "etcet", "etset", "ēt",
    "eyēt", "atsket", "acket", "atset", "akēt",
)
PAST_TWO_ENDINGS = ("ivnks", "etskvnks", "eckvnks", "eccvnks", "etcvnks", "vnks", "ēyvnks", "atskvnks", "ackvnks", "akvnks")
PAST_THREE_ENDINGS = ("imvts", "etskemvts", "eckemvts", "eccemvts", "etcemvts", "emvts", "ēyemvts", "atskemvts", "ackemvts", "akemvts")
PAST_FOUR_ENDINGS = ("vntv", "vntvs")
PAST_FIVE_ENDINGS = ("akvtē", "eckvtē","vtē", "vtēs", "vtes")
VHAN_AUXILIARY_ENDINGS = (
    "vhanit", "vhanetsket", "vhanecket", "vhaneccet",
    "vhanetcet", "vhanetset", "vhanet", "vhanēt", "vhanatsket",
    "vhanacket", "vhanatset", "vkvhanet",
)


def fold(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if unicodedata.category(char) != "Mn"
    ).lower()


def l_grade(stem: str) -> str:
    """Present-tense L-grade"""
    i = next((i for i in range(len(stem) - 1, -1, -1) if stem[i] in VOWELS), None)
    if i is None or (i > 0 and stem[i - 1:i + 1] == "ue"):
        return stem
    if i + 2 < len(stem) and stem[i + 1] in "lmn" and stem[i + 2] in "cfhklmnprstw":
        return stem
    return stem[:i] + {"v": "a", "e": "ē"}.get(stem[i], stem[i]) + stem[i + 1:]


def h_grade(stem: str) -> tuple[str, bool] | None:
    """Past-one H-grade and whether its special third-plural rule applies."""
    if stem.endswith(("uec", "uek")):
        return stem[:-1] + "h" + stem[-1], False
    if len(stem) >= 3 and stem[-3:-1] == "ue" and stem[-1] in CONSONANTS:
        return stem[:-3] + "uyi" + stem[-1], False
    if stem.endswith("vok"):
        return stem[:-3] + "vwik", False
    i = next((i for i in range(len(stem) - 1, -1, -1) if stem[i] in VOWELS), None)
    if i is None:
        return None
    ending = stem[i + 1:]
    if len(ending) == 2 and ending[0] == ending[1] and ending != "kk":
        return stem[:-1] + "iy", False
    if len(ending) >= 2 and all(char in CONSONANTS for char in ending):
        return stem[:-1] + "i" + stem[-1], False
    replacement = {"a": "vh", "e": "eh", "ē": "eh", "i": "ih", "o": "oh", "u": "uh", "v": "vh"}
    return stem[:i] + replacement[stem[i]] + ending, True


def stative_stems(lemma: str, regular_plural: bool) -> tuple[str, ...]:
    """Regular stative present stems before the final -s."""
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


def stative_derivations(stem: str) -> set[str]:
    """diminutive and vowel-lengthened augmentative forms."""
    root = stem[:-1]
    bases = {root}
    index = next((i for i in range(len(root) - 1, -1, -1) if root[i] in "ve"), None)
    if index is not None:
        grade = {"v": "a", "e": "ē"}[root[index]]
        bases.add(root[:index] + grade + root[index + 1:])
        nasal = {"v": "ą", "e": "ę̄"}[root[index]]
        bases.add(unicodedata.normalize("NFC", root[:index] + nasal + root[index + 1:]))
    return {base + ending for base in bases for ending in ("usē", "ose")}


def literal(text: str) -> str:
    # RLG normally treats spaces and apostrophes as syntax.
    return "".join("\\" + char for char in text)


class Morphology:
    def __init__(self, lift: Path):
        self.entry_ids: dict[str, list[str]] = {}
        self.lemma_order: dict[str, int] = {}
        self.headwords: dict[str, str] = {}
        self.categories: dict[str, set[str]] = {}
        self.irregular_plural: set[str] = set()
        entries_by_id: dict[str, str] = {}
        ids_by_key: dict[str, str] = {}
        variant_refs: dict[str, list[str]] = {}
        plural_refs: dict[str, set[str]] = {}
        seen_senses: set[str] = set()
        for _, entry in ET.iterparse(lift, events=("end",)):
            if entry.tag != "entry":
                continue
            entry_id = entry.get("id")
            if not entry_id or not entry_id.strip():
                raise ValueError(f"{lift}: missing entry id")
            entry_key = unicodedata.normalize("NFC", entry_id)
            if entry_key in ids_by_key:
                raise ValueError(f"{lift}: duplicate entry id {entry_id!r}")
            ids_by_key[entry_key] = entry_id
            for node in entry.findall("./relation"):
                if node.get("type") == "_component-lexeme" and any(
                    trait.get("name") == "variant-type" and trait.get("value") == "Free Variant"
                    for trait in node.findall("./trait")
                ):
                    ref = node.get("ref")
                    if not ref or not ref.strip():
                        warnings.warn(f"{lift}: free variant {entry_id!r} has no reference", stacklevel=2)
                    else:
                        variant_refs.setdefault(entry_key, []).append(unicodedata.normalize("NFC", ref))
            text = entry.find("./lexical-unit/form[@lang='mus']/text")
            if text is not None and text.text and text.text.strip():
                headword = text.text.strip()
                lemma = unicodedata.normalize("NFC", headword).lower()
                etem_verb = (
                    lemma.startswith("etem ") and lemma.endswith("etv")
                    and not any(char.isspace() for char in lemma[5:])
                )
                if etem_verb or not any(char.isspace() for char in lemma):
                    entries_by_id[entry_key] = lemma
                    self.entry_ids.setdefault(lemma, []).append(entry_id)
                    self.headwords.setdefault(lemma, headword)
                    categories = self.categories.setdefault(lemma, set())
                    for sense in entry.findall(".//sense"):
                        sense_id = sense.get("id")
                        if not sense_id or not sense_id.strip():
                            raise ValueError(f"{lift}: missing sense id for {headword!r}")
                        if sense_id in seen_senses:
                            raise ValueError(f"{lift}: duplicate sense id {sense_id!r}")
                        self.lemma_order.setdefault(lemma, len(seen_senses))
                        seen_senses.add(sense_id)
                        category = sense.find("./grammatical-info")
                        category_value = category.get("value") if category is not None else None
                        if category_value:
                            categories.add(category_value)
                    if any(node.get("type") in {"EntryPl", "EntryDu", "EntryTpl"} for node in entry.findall("./relation")):
                        self.irregular_plural.add(lemma)
                    for node in entry.findall("./relation"):
                        ref = node.get("ref")
                        if node.get("type") in {"EntryDu", "EntryTpl"} and ref:
                            plural_refs.setdefault(lemma, set()).add(unicodedata.normalize("NFC", ref))
            entry.clear()

        for source, refs in variant_refs.items():
            for ref in refs:
                if ref not in ids_by_key:
                    warnings.warn(
                        f"{lift}: free variant {ids_by_key[source]!r} references missing entry {ref!r}",
                        stacklevel=2,
                    )
        for lemma, entry_ids in self.entry_ids.items():
            pending = deque(unicodedata.normalize("NFC", entry_id) for entry_id in entry_ids)
            seen = set(pending)
            while pending:
                for ref in variant_refs.get(pending.popleft(), []):
                    if ref in seen or ref not in ids_by_key:
                        continue
                    seen.add(ref)
                    entry_ids.append(ids_by_key[ref])
                    pending.append(ref)
        self.sense_count = len(seen_senses)

        grammar: dict[str, list] = {"Root": []}
        past_five_endings = tuple(dict.fromkeys(
            PAST_FIVE_ENDINGS + tuple(ending + "s" for ending in PAST_FIVE_ENDINGS if not ending.endswith("s"))
        ))
        present_adverbs = tuple(ending[:-1] + "n" for ending in PRESENT_ENDINGS)
        plural_adverbs = tuple(ending[:-1] + "n" for ending in PRESENT_ENDINGS[7:-1] + ("es",))
        for state, endings, singular in (
            ("Present", PRESENT_ENDINGS, PRESENT_ENDINGS[:7]),
            ("PresentAdverb", present_adverbs, present_adverbs[:7]),
            ("Past", PRESENT_ENDINGS[:-1], PRESENT_ENDINGS[:7]),
            ("Future", FUTURE_ENDINGS, FUTURE_ENDINGS[:3]),
            ("Vhan", VHAN_ENDINGS, VHAN_ENDINGS[:7]),
            ("Imperative", IMPERATIVE_ENDINGS, ("vs", "epvs", "ekot", "vkēs", "ekvs", "vccvs")),
            ("Auxiliary", AUXILIARY_ENDINGS, AUXILIARY_ENDINGS[:7]),
            ("VhanAuxiliary", VHAN_AUXILIARY_ENDINGS, VHAN_AUXILIARY_ENDINGS[:7]),
            ("PastTwo", PAST_TWO_ENDINGS, PAST_TWO_ENDINGS[:6]),
            ("PastThree", PAST_THREE_ENDINGS, PAST_THREE_ENDINGS[:6]),
            ("PastFour", PAST_FOUR_ENDINGS, PAST_FOUR_ENDINGS),
            ("PastFive", past_five_endings, past_five_endings),
            ("VerbAdverb", ("en", "ēn", "aken"), ("en", "ēn", "aken")),
            ("Stative", ("s", "tis", "n", ""), ("s", "tis", "n", "")),
            ("Subject", ("t",), ("t",)),
            ("DirectObject", ("n",), ("n",)),
            ("DefiniteSubject", ("at",), ("at",)),
            ("PresentPlural", PRESENT_ENDINGS[7:-1] + ("es",), PRESENT_ENDINGS[7:-1] + ("es",)),
            ("PresentAdverbPlural", plural_adverbs, plural_adverbs),
            ("FuturePlural", FUTURE_ENDINGS[3:5] + ("vrēs",), FUTURE_ENDINGS[3:5] + ("vrēs",)),
            ("VhanPlural", VHAN_ENDINGS[7:-1] + ("vhanvnks",), VHAN_ENDINGS[7:-1] + ("vhanvnks",)),
            ("ImperativePlural", ("vks", "epvs", "ekot", "vkēs", "vkēts", "vkvccvs"), ("vks", "epvs", "ekot", "vkēs", "vkēts", "vkvccvs")),
            ("AuxiliaryPlural", AUXILIARY_ENDINGS[7:-1] + ("ēt",), AUXILIARY_ENDINGS[7:-1] + ("ēt",)),
            ("VhanAuxiliaryPlural", VHAN_AUXILIARY_ENDINGS[7:-1] + ("vhanēt",), VHAN_AUXILIARY_ENDINGS[7:-1] + ("vhanēt",)),
            ("PastTwoPlural", PAST_TWO_ENDINGS[6:9] + ("vnks",), PAST_TWO_ENDINGS[6:9] + ("vnks",)),
            ("PastThreePlural", PAST_THREE_ENDINGS[6:9] + ("vnks",), PAST_THREE_ENDINGS[6:9] + ("vnks",)),
            ("PastFourPlural", PAST_FOUR_ENDINGS, PAST_FOUR_ENDINGS),
            ("PastFivePlural", past_five_endings, past_five_endings),
            ("PastPlural", PRESENT_ENDINGS[7:-1], PRESENT_ENDINGS[7:-1]),
        ):
            grammar[state] = [(("", literal(ending)), "#") for ending in endings]
            grammar[state + "Fold"] = [(("", literal(fold(ending))), "#") for ending in endings]
            grammar[state + "Singular"] = [(("", literal(ending)), "#") for ending in singular]
            grammar[state + "SingularFold"] = [(("", literal(fold(ending))), "#") for ending in singular]
        for lemma in self.entry_ids:
            self._add_root(grammar, lemma, lemma, "#")
            self._add_root(grammar, lemma, lemma, "Subject")
            self._add_root(grammar, lemma, lemma, "DirectObject")
            if lemma.endswith(("e", "ē")):
                self._add_root(grammar, lemma, lemma[:-1], "DefiniteSubject")
                categories = self.categories.get(lemma, set())
                if not categories or categories & {"adjective", "adj", "stative"}:
                    self._add_root(grammar, lemma, lemma[:-1], "PastFive")
            elif lemma.endswith("etv"):
                self._add_root(grammar, lemma, lemma[:-3], "DefiniteSubject")
            if "numeral" in self.categories.get(lemma, set()) and lemma.endswith("en"):
                self._add_root(grammar, lemma, lemma[:-1], "#")
            if self.categories.get(lemma, set()) & {"adjective", "adj", "stative"} and lemma.endswith(("e", "ē")):
                for surface in stative_stems(lemma, lemma not in self.irregular_plural):
                    self._add_root(grammar, lemma, surface, "Stative")
                    for derived in stative_derivations(surface):
                        self._add_root(grammar, lemma, derived, "Stative")
            # Action candidates use the -etv ending.
            if not lemma.endswith("etv") or lemma == "ometv" or len(lemma) <= 4:
                continue
            base = lemma[:-3]
            if not any(char in VOWELS for char in base.rsplit(" ", 1)[-1]):
                continue
            singular = "Singular" if lemma in self.irregular_plural else ""
            self._add_root(grammar, lemma, base, "Future" + singular)
            self._add_root(grammar, lemma, base, "Vhan" + singular)
            self._add_root(grammar, lemma, base, "VhanAuxiliary" + singular)
            self._add_root(grammar, lemma, base, "PastTwo" + singular)
            self._add_root(grammar, lemma, base, "PastThree" + singular)
            for state in ("PastFour", "PastFive"):
                self._add_root(grammar, lemma, base, state + singular)
                self._add_root(grammar, lemma, "en" + base, state + singular)
            self._add_root(grammar, lemma, base, "VerbAdverb")
            self._add_root(grammar, lemma, base + "eko", "#")
            self._add_root(grammar, lemma, lemma[:-2], "#")
            self._add_root(grammar, lemma, base, "Imperative" + singular)
            self._add_root(grammar, lemma, l_grade(base), "Present" + singular)
            self._add_root(grammar, lemma, l_grade(base), "PresentAdverb" + singular)
            self._add_root(grammar, lemma, l_grade(base), "Auxiliary" + singular)
            self._add_root(grammar, lemma, base + "et", "#")
            past = h_grade(base)
            if past:
                past_base, basic = past
                self._add_root(grammar, lemma, past_base, "Past" + singular)
                self._add_root(grammar, lemma, past_base + "et", "#")
                if not singular:
                    plural_base = h_grade(base + "ak") if basic else None
                    self._add_root(grammar, lemma, (plural_base[0] + "es") if plural_base else (past_base + "akes"), "#")
            for ref in plural_refs.get(lemma, set()):
                alternate = entries_by_id.get(ref)
                if alternate is None or not alternate.endswith("etv"):
                    continue
                plural_base = alternate[:-3]
                if not any(char in VOWELS for char in plural_base):
                    continue
                for state in ("Future", "Vhan", "VhanAuxiliary", "PastTwo", "PastThree", "PastFour", "PastFive", "Imperative"):
                    self._add_root(grammar, lemma, plural_base, state + "Plural")
                for state in ("PastFour", "PastFive"):
                    self._add_root(grammar, lemma, "en" + plural_base, state + "Plural")
                for state in ("Present", "PresentAdverb", "Auxiliary"):
                    self._add_root(grammar, lemma, l_grade(plural_base), state + "Plural")
                self._add_root(grammar, lemma, plural_base + "et", "#")
                past = h_grade(plural_base)
                if past:
                    past_base, basic = past
                    self._add_root(grammar, lemma, past_base, "PastPlural")
                    self._add_root(grammar, lemma, past_base + "et", "#")
                    third = h_grade(plural_base + "ak") if basic else None
                    self._add_root(grammar, lemma, (third[0] + "es") if third else (past_base + "akes"), "#")
        grammar["UnprefixedRoot"] = grammar["Root"]
        grammar["Root"] = [(("", ""), "UnprefixedRoot")] + [
            (("", literal(prefix)), "UnprefixedRoot", 2) for prefix in POSSESSIVE_PREFIXES
        ]
        self.fst = FST.rlg(grammar, "Root")

    @staticmethod
    def _add_root(grammar: dict[str, list], lemma: str, surface: str, state: str) -> None:
        surfaces = [(surface, 0)]
        if lemma.startswith("etem ") and surface.startswith("etem "):
            surfaces.append((surface.replace(" ", "", 1), 2))
        for variant, weight in tuple(surfaces):
            if variant.startswith("e") and len(variant) > 1:
                surfaces.extend((prefix + variant[1:], weight + 2) for prefix in ("", "'", "’"))
        for variant, contraction_weight in surfaces:
            for spelling, folded in ((variant, False), (fold(variant), True)):
                prefix = spelling[:2]
                prefix_state = "Prefix:" + prefix
                if prefix_state not in grammar:
                    grammar["Root"].append((("", literal(prefix)), prefix_state))
                    grammar[prefix_state] = []
                target = state + "Fold" if folded and state != "#" else state
                grammar[prefix_state].append(
                    ((literal(lemma), literal(spelling[2:])), target, contraction_weight + int(folded))
                )

    def analyze(self, word: str) -> tuple[str | None, list[str]]:
        word = unicodedata.normalize("NFC", word).lower().strip(",")
        for lookup in (self._analyze_exact, self._analyze_fuzzy):
            result = lookup(word)
            if result is not None:
                return result
            result = self._analyze_combined(word, lookup)
            if result is not None:
                return result
        return None, []

    def _analyze_exact(self, word: str) -> tuple[str, list[str]] | None:
        # A dictionary headword is less speculative than an inflected analysis.
        if word in self.entry_ids:
            return self.headwords[word], self.entry_ids[word].copy()
        for spelling in dict.fromkeys((word, fold(word))):
            candidates = [(cast(str, lemma), weight) for lemma, weight in self.fst.analyze(spelling, weights=True)]
            if candidates:
                return self._select_candidate(candidates)
        return None

    def _analyze_combined(
        self, word: str, lookup: Callable[[str], tuple[str, list[str]] | None]
    ) -> tuple[str, list[str]] | None:
        for prefix in ("em", "m"):
            if not word.startswith(prefix) or len(word) == len(prefix):
                continue
            surface = word[len(prefix):]
            result = lookup(surface)
            if result is None:
                continue
            stem, ids = result
            lemma = unicodedata.normalize("NFC", stem).lower()
            if not lemma.endswith("etv") and "verb" not in self.categories.get(lemma, set()):
                continue
            return f"em {surface}", list(dict.fromkeys(self.entry_ids.get("em", []) + ids))
        return None

    def _analyze_fuzzy(self, word: str) -> tuple[str, list[str]] | None:
        spelling = fold(word)
        if not any(char in FUZZY_ALTERNATES or char == "c" for char in spelling):
            return None
        grammar: dict[str, list[tuple[tuple[str, str], str, int]]] = {}
        for i, char in enumerate(spelling):
            target = "#" if i == len(spelling) - 1 else str(i + 1)
            rules = [((literal(char), literal(char)), target, 0)]
            if char in FUZZY_ALTERNATES:
                # FST paths cost at most 7, so a fuzzy edit must cost more.
                rules.append(((literal(FUZZY_ALTERNATES[char]), literal(char)), target, 8))
            if char == "c":
                previous_is_c = i > 0 and spelling[i - 1] == "c"
                next_is_c = i + 1 < len(spelling) and spelling[i + 1] == "c"
                if not previous_is_c and not next_is_c:
                    rules.append(((literal("cc"), literal("c")), target, 8))
                if not previous_is_c and next_is_c and (i + 2 == len(spelling) or spelling[i + 2] != "c"):
                    doubled_target = "#" if i + 2 == len(spelling) else str(i + 2)
                    rules.append(((literal("c"), literal("cc")), doubled_target, 8))
            grammar[str(i)] = rules
        variants = FST.rlg(grammar, "0")
        fst = self.fst
        if "." in fst.alphabet and variants.alphabet - fst.alphabet:
            fst = copy(fst)
        fuzzy_fst = algorithms.compose(fst, variants)
        candidates = [(cast(str, lemma), weight) for lemma, weight in fuzzy_fst.analyze(spelling, weights=True)]
        if candidates:
            return self._select_candidate(candidates)
        return None

    def _select_candidate(self, candidates: list[tuple[str, float]]) -> tuple[str, list[str]]:
        lemma, _ = min(candidates, key=lambda item: (
            item[1],
            self.lemma_order.get(item[0], self.sense_count),
            item[0],
        ))
        return self.headwords[lemma], self.entry_ids[lemma].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("words", nargs="+", help="surface words to analyze")
    parser.add_argument("--lexicon", type=Path, default=DEFAULT_LEXICON, help="dictionary LIFT file")
    args = parser.parse_args()
    analyzer = Morphology(args.lexicon)
    for word in args.words:
        word = word.strip(",")
        if not word:
            continue
        stem, entry_ids = analyzer.analyze(word)
        print(json.dumps({"word": word, "stem": stem, "ids": entry_ids}, ensure_ascii=False))


if __name__ == "__main__":
    main()
