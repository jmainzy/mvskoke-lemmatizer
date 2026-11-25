"""Analyze words from a UTF-8 text file with an HFST optimized-lookup analyzer."""

import argparse
import csv
from functools import lru_cache
from itertools import combinations, product
from pathlib import Path
import unicodedata

import pyhfst


DEFAULT_ANALYZER = Path(__file__).resolve().parent / "analyzer.hfstol"

ALTERNATES = {
    "a": (("ą", 1), ("v", 2)), "ą": (("a", 1),),
    "e": (("ē", 1), ("ę", 1), ("ę̄", 1)),
    "ē": (("e", 1), ("ę̄", 1)), "ę": (("e", 1), ("ę̄", 1)),
    "ę̄": (("e", 1), ("ē", 1), ("ę", 1)),
    "i": (("į", 1),), "į": (("i", 1),),
    "o": (("ǫ", 1), ("u", 2)), "ǫ": (("o", 1),),
    "u": (("ų", 1), ("o", 2)), "ų": (("u", 1),),
    "v": (("a", 2),), "f": (("h", 2),),
}


@lru_cache(maxsize=1)
def _default_transducer():
    return _load_transducer(DEFAULT_ANALYZER)


def _load_transducer(path):
    transducer = pyhfst.HfstInputStream(str(path)).read()
    transducer.cache = False
    return transducer


def _alternatives(word):
    letters = []
    for char in word:
        if unicodedata.combining(char) and letters:
            letters[-1] += char
        else:
            letters.append(char)
    positions = [index for index, char in enumerate(letters) if char in ALTERNATES]
    for total_cost in range(1, 5):
        for count in (1, 2):
            for indices in combinations(positions, count):
                for replacements in product(*(ALTERNATES[letters[index]] for index in indices)):
                    if sum(cost for _, cost in replacements) != total_cost:
                        continue
                    variant = letters.copy()
                    for index, (replacement, _) in zip(indices, replacements):
                        variant[index] = replacement
                    yield total_cost, "".join(variant)


def analyze(word, transducer=None, *, fuzzy=True):
    """Return all exact analyses, or the closest fuzzy analyses when none exist."""
    word = unicodedata.normalize("NFC", word).lower()
    transducer = _default_transducer() if transducer is None else transducer
    exact = list(dict.fromkeys(analysis for analysis, _ in transducer.lookup(word)))
    if exact or not fuzzy:
        return exact
    matches = []
    best_cost = None
    for cost, variant in _alternatives(word):
        if best_cost is not None and cost > best_cost:
            break
        analyses = [analysis for analysis, _ in transducer.lookup(variant)]
        if analyses:
            best_cost = cost
            matches.extend(analyses)
    return list(dict.fromkeys(matches))


def read_lines(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [[word.lower() for word in line.split()] for line in f]


def read_file(filename):
    return [word for line in read_lines(filename) for word in line]


def analyze_lines(lines, transducer):
    results = []
    for line in lines:
        for index, token in enumerate(line):
            word = token.strip(",?")
            if not word:
                continue
            results.append((word, analyze(word, transducer)))
            phrase = word
            previous = token
            for next_token in line[index + 1:index + 3]:
                if previous.endswith((",", "?")) or next_token.startswith((",", "?")):
                    break
                next_word = next_token.strip(",?")
                if not next_word:
                    break
                phrase += f" {next_word}"
                analyses = [
                    result for result in analyze(phrase, transducer)
                    if result.startswith(("+Dative", "+Possessive", "+Comitative", "+Compare"))
                ]
                if analyses:
                    results.append((phrase, analyses))
                previous = next_token
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="UTF-8 text file to analyze")
    parser.add_argument("--output", type=Path, default=Path("analysis_results.tsv"),
                        help="output TSV file (default: analysis_results.tsv)")
    parser.add_argument("--analyzer", type=Path, default=DEFAULT_ANALYZER,
                        help="compiled HFST optimized-lookup analyzer")
    args = parser.parse_args()
    protected_paths = (args.file, args.analyzer)
    if any(args.output.resolve() == path.resolve() or
           (args.output.exists() and path.exists() and args.output.samefile(path))
           for path in protected_paths):
        parser.error("output must be different from the input text and analyzer files")

    lines = read_lines(args.file)
    transducer = _load_transducer(args.analyzer)
    results = analyze_lines(lines, transducer)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(["word", "analysis"])
        writer.writerows(results)


if __name__ == "__main__":
    main()
