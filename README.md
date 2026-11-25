# Lemmatizing and Morphological Segmentation for Mvskoke

HFST (Helsinki finite-state transducer) with some backup fuzzy matching for the Muscogee (Creek) language.

## Usage

Install requirements:  
`python -m venv .venv`  
`source .venv/bin/activate`  
`python -m pip install -r requirements.txt`

Build the HFST:  
`python src/build.py`

**Morpholocial Analysis**  
To do an analysis:  
`python src/analyze.py example.txt`

Output will be a .tsv file with the associated analysis:

```
nettv	['nettv+Unknown']
onvkuce	['onvkuce+N']
Punvttv	[]
omvlkvt	['omvlkv+AdjN+Subject']
eto	['eto+N']
ofv	['ofv+N', 'ofv+Post']
fullat	['fulletv+N+DefiniteSubject', 'fulletv+V+DefiniteSubject']
```

**Lemmatizing**  
Output will be words with their stem and associated dictionary entry id:

```
{"word": "pale", "stem": "palen", "ids": ["palen_c865559e-7944-4f00-8619-bb27c44d01f2"]}
{"word": "tvlkosen", "stem": "tvlkē", "ids": ["tvlkē_41259274-734b-4a5b-ac1b-f4b30dfd2733"]}
{"word": "mecvtes", "stem": "mēcetv", "ids": ["mēcetv_1b547f03-048d-4917-b423-980e6576c478"]}
```

## Exporting the Lexicon

To build the Lexicon you'll need the dictionary. Make sure you have access to the `lexicon.lift` file.
Generate `src/lexicon.lexc` file with:

```
python src/export_lexicon.py --lift path/to/lexicon.lift
```

## Editing the rules

Add and change rules in `morphology.lexc` and `phonology.twol` (under the `src/` folder).

Once you've made your changes, run `python src/build.py` to compile the generated lexicon together with those rules, and do the analysis again.

## Notes

This is **not yet a complete port** of the existing lemmatizer. It currently
covers verb endings, L- and H-grades, linked dual/triplural verb stems,
subject and object suffixes, definite subjects, numeral bases, and stative
past forms. Possessive prefixes, the `en` past prefix, initial contractions, joined `etem` and `em`
forms, stative present and derived forms, past third-plural special forms,
case and accent normalization, fuzzy matching, ranking, and dictionary entry
IDs are not yet implemented.

## Tests

Run the exporter tests with:

```
python -m unittest discover -s tests -p test_export_lexicon.py
```

The grammar tests use the separate `hfst` Python bindings:

```
python -m unittest discover -s tests -p test_hfst_grammar.py
```
