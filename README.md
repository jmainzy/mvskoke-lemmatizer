# Lemmatizing and Morphological Segmentation for Mvskoke

HFST (Helsinki finite-state transducer) morphological analysis for the Muscogee (Creek) language.

## Usage

Download or clone the code and install:

```sh
python -m pip install /path/to/mvskoke-lemmatizer
```

```python
from mvskoke_lemmatizer import analyze, lemmatize

analyses = analyze("punvttv")       # includes "ponvttv+N"
lemmas = lemmatize("nere")         # ["nerē"]
```

`analyze()` returns a list of HFST analysis strings and `lemmatize()` returns
all distinct base lemmas.

**Lemmatization**

Run `python src/lemmatize.py example.txt` or the installed
`mvskoke-lemmatize example.txt`. Both write `lemmatize_results.tsv` by default;
use `--output path.tsv` to choose another output file.

**Morphological analysis**

To analyze a text file, run `python src/analyze.py example.txt` or the installed
`mvskoke-analyze example.txt` command.

Output will be a .tsv file with the associated analysis:

```
nettv	['nettv+Unknown']
onvkuce	['onvkuce+N']
punvttv	['+Possessive3+ponvttv+N', 'ponvttv+N']
omvlkvt	['omvlkv+AdjN+Subject']
eto	['eto+N']
ofv	['ofv+N', 'ofv+Post']
fullat	['fulletv+N+DefiniteSubject', 'fulletv+V+DefiniteSubject']
```

## Updating the Lexicon

To build the lexicon you'll need the dictionary. Make sure you have access to the `lexicon.lift` file.
Generate `grammar/lexicon.lexc` with:

```
python src/export_lexicon.py --lift path/to/lexicon.lift
```

## Building the HFST

If you edit the grammar, you'll need to re-build the hfst.

Install python requirements:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Build:

```
python src/build.py
```

The build writes `build/analyzer.hfstol` and the package's
`src/analyzer.hfstol`. Rebuild before packaging when the grammar changes.

## Editing the rules

Add and change rules under the `grammar/` folder (except `lexicon.lexc`, which is generated).

Once you've made your changes, run `python src/build.py` to compile the generated lexicon together with those rules, and do the analysis again.

For more info about the details of the grammar, see [Notes](./notes.md)
