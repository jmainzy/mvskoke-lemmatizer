"""Analyze words from a UTF-8 text file with an HFST optimized-lookup analyzer."""

import argparse
import csv
from pathlib import Path

import pyhfst


DEFAULT_ANALYZER = Path(__file__).resolve().parent.parent / "build" / "analyzer.hfstol"


def analyze(word, transducer):
    return [analysis for analysis, _ in transducer.lookup(word)]


def read_file(filename):
    words = []
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            words.extend(line.strip().split())
    return words


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

    words = [word.strip(",") for word in read_file(args.file)]
    transducer = pyhfst.HfstInputStream(str(args.analyzer)).read()
    results = [(word, analyze(word, transducer)) for word in words if word]
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, delimiter="\t", lineterminator="\n")
        writer.writerow(["word", "analysis"])
        writer.writerows(results)


if __name__ == "__main__":
    main()
