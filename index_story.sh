#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate

sample_file="example.txt"

# read the file
words=$(<"$sample_file")
# split the words
IFS=' ' read -r -a words_array <<< "$words"
# segmenter
python segment.py "${words_array[@]}" > "example.json"