# Notes

Both analyze and lemmatize return `[]` for an
unrecognized word. They lowercase and NFC-normalize input; punctuation should
be removed before calling them. Pass `fuzzy=False` to require an exact match.
The model is loaded once on the first call.

Fuzzy lookup runs only if there are no exact analyses. It tries up to two
character substitutions: vowel diacritics (cost 1), `a`/`v`, `o`/`u`, and
`f` → `h` (cost 2). All analyses at the lowest total cost are returned.
This is not general spelling correction and does not insert or delete letters.
This analyzer covers verb endings, L- and H-grades, past third-plural special forms,
linked dual/triplural verb stems, subject and object suffixes, definite
subjects, numeral bases, and stative present, derived, and past forms.
Stative analyses use `+Stative`, optional person/number tags such as
`+FirstPlural`, and `+Derived` for derived forms. The special third-plural
past is tagged `+Past1+ThirdPlural`.
Verb person markers follow the patient and dative patterns in
[Mvskoke Language Patterns: Person markers](https://viva.pressbooks.pub/mvskokelanguagepatterns/chapter/person-markers/).
Their tags precede the lemma, for example
`+Dative2+Patient1S+cvpakketv+V+Present`. Patient tags are `+Patient1S`,
`+Patient2`, `+Patient1P`, `+PatientReflexive`, and `+PatientReciprocal`;
dative tags are `+Dative1S`, `+Dative2`, `+Dative3`, `+Dative1P`, and
`+DativeReciprocal`. An unmarked third-person patient is not tagged.
For patient-marked forms, `-ēs` is also allowed on the ungraded stem.
Marker compatibility is permissive: verb-specific argument classes and
person combinations are not checked, and separated dative forms are allowed
before consonants as well as vowels.

Noun possessives use `+Possessive1S`, `+Possessive2`, `+Possessive3`, and
`+Possessive1P` before the lemma, for example `+Possessive1S+enke+N` for
`cvnke`. The `cv` and `vm` classes follow the supplied possession reference.
Unclassified dictionary nouns accept both classes, so some analyses may be
linguistically invalid; classify them in `possessive_nouns.tsv` to restrict
them. The optional third-person `e-` of `cv` nouns also permits an unmarked
third-person analysis. The reference does not specify `cv` allomorphs before
initial `v`, `i`, or `u`, so those forms are not generated.

The adverb rules add `+Manner` to adjectives, and `+TimeRecent` or
`+TimeEarlier` to the selected time-word entries. Verb negative forms use
`+Negative`, an `+Agent...` tag, and `+Statement` or `+Question`; stative
adjectives also accept the illustrated negative `-ekot`. Instrumental
`+Instrumental`, person-with `+Comitative...`, and comparison `+Compare...`
tags precede the lemma. The instrumental present of `vyetv` includes the
two patient forms illustrated in the reference. Comparative agent endings
are limited to the forms illustrated there; the complete comparative
paradigm is not specified in the reference.

Initial contractions and the previous lemmatizer's additional joined spellings of
dictionary entries beginning with `etem ` and `em ` are not yet implemented.
Dictionary entry IDs are also deferred.

## Tests

Run the exporter tests with:

```
python -m unittest discover -s tests -p test_export_lexicon.py
```

The grammar tests use the separate `hfst` Python bindings:

```
python -m unittest discover -s tests -p test_hfst_grammar.py
```
