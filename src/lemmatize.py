"""Extract dictionary lemmas from morphological analyses."""

import argparse
import csv
from pathlib import Path

if __package__:
    from .analyze import analyze
else:
    from analyze import analyze

PARTS_OF_SPEECH = {
    "N", "V", "Adj", "Adv", "Num", "Interj", "Part", "Pron", "AdjN",
    "Post", "Conn", "AuxV", "Dem", "Suff", "Pref", "Unknown",
}


def lemmatize(word, *, fuzzy=True):
    """Return all distinct dictionary lemmas for a word or phrase."""
    lemmas = []
    for analysis in analyze(word, fuzzy=fuzzy):
        parts = analysis.split("+")
        for index in range(1, len(parts)):
            if parts[index] in PARTS_OF_SPEECH:
                lemmas.append(parts[index - 1])
                break
        else:
            raise ValueError(f"analysis has no recognized part of speech: {analysis!r}")
    return list(dict.fromkeys(lemmas))

def read_lines(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [[word.lower() for word in line.split()] for line in f]


def read_file(filename):
    return [word for line in read_lines(filename) for word in line]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="UTF-8 text file to analyze")
    parser.add_argument("--output", type=Path, default=Path("lemmatize_results.tsv"),
                        help="output TSV file (default: lemmatize_results.tsv)")
    args = parser.parse_args()

    lines = read_lines(args.file)
    results = []
    for line in lines:
        for word in line:
            for lemma in lemmatize(word):
                results.append((word, lemma))

    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(["word", "lemma"])
        writer.writerows(results)


if __name__ == "__main__":
    main()
