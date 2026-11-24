# Morphological Segmentation for Mvskoke
FST (finite-state transducer) with some backup fuzzy matching for the Muscogee (Creek) language.

## Run 
You'll need the dictionary. Make sure you have access to the `lexicon.lift` file.

Install requirements:  
`python -m venv .venv`
`source .venv/bin/activate`  
`python -m pip install -r requirements.txt`


Run with:  
`python segment.py "pale", "tvlkosen", "mecvtes"`

output will be words with their stem and associated dictionary entry id:
```
{"word": "pale", "stem": "palen", "ids": ["palen_c865559e-7944-4f00-8619-bb27c44d01f2"]}
{"word": "tvlkosen", "stem": "tvlkē", "ids": ["tvlkē_41259274-734b-4a5b-ac1b-f4b30dfd2733"]}
{"word": "mecvtes", "stem": "mēcetv", "ids": ["mēcetv_1b547f03-048d-4917-b423-980e6576c478"]}
```

## Example Text
Run `bash index_story.sh` to analyze `example.txt`. 
