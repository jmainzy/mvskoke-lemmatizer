import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch

from src import analyze, lemmatize

lemmatizer = importlib.import_module("src.lemmatize")


class LibraryTests(TestCase):
    def test_lemmatize_script_runs_outside_project_directory(self):
        script = Path(__file__).resolve().parents[1] / "src" / "lemmatize.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.txt"
            output = root / "output.tsv"
            source.write_text("punvttv nere ton ele\n", encoding="utf-8")
            subprocess.run(
                [sys.executable, str(script), str(source), "--output", str(output)],
                cwd=root, check=True, capture_output=True, text=True,
            )
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "word\tlemma\npunvttv\tponvttv\nnere\tnerē\nton\tton\nele\tele\n",
            )

    def test_examples_and_normalization(self):
        self.assertIn("ponvttv+N", analyze("Punvttv"))
        self.assertIn("nerē+N", analyze("nere"))
        self.assertEqual(lemmatize("punvttv"), ["ponvttv"])
        self.assertEqual(lemmatize("nere"), ["nerē"])
        self.assertEqual(lemmatize("NERE\u0304"), ["nerē"])

    def test_fuzzy_inflected_forms_and_disabling_fuzzy(self):
        self.assertIn("nerē", lemmatize("neret"))
        self.assertEqual(analyze("punvttv", fuzzy=False), [])
        self.assertEqual(lemmatize("punvttv", fuzzy=False), [])
        self.assertEqual(lemmatize("not_a_word"), [])

    def test_prefers_exact_then_closest_and_keeps_ties(self):
        transducer = Mock()
        answers = {
            "puna": [("exact+N", 0)],
            "pona": [("one+N", 0), ("one+Adj", 0)],
            "punv": [("other+N", 0)],
            "ponv": [("two+N", 0)],
        }
        transducer.lookup.side_effect = lambda word: answers.get(word, [])
        self.assertEqual(analyze("puna", transducer), ["exact+N"])
        transducer.lookup.assert_called_once_with("puna")
        transducer.reset_mock()
        del answers["puna"]
        self.assertEqual(set(analyze("puna", transducer)), {"one+N", "one+Adj", "other+N"})
        self.assertNotIn("ponv", [call.args[0] for call in transducer.lookup.call_args_list])

    def test_accent_changes_are_preferred_and_fuzzy_does_not_insert_letters(self):
        transducer = Mock()
        answers = {"pona": [("vowel+N", 0)]}
        transducer.lookup.side_effect = lambda word: answers.get(word, [])
        self.assertEqual(analyze("puna", transducer), ["vowel+N"])
        answers["puna"] = []
        answers["puną"] = [("accent+N", 0)]
        self.assertEqual(analyze("puna", transducer), ["accent+N"])
        self.assertEqual(analyze("pon", transducer), [])

    def test_longest_lemma_including_prefix_markers(self):
        with patch.object(lemmatizer, "analyze", return_value=[
            "+Dative2+Patient1S+cvpakketv+V+Present",
            "+Patient1S+cvpakketv+V+Present",
            "cvpakkē+Adj+Stative+First",
            "+DativeReciprocal+etem punahoyetv+V",
        ]):
            self.assertEqual(lemmatize("word"), ["etem punahoyetv"])
        with patch.object(lemmatizer, "analyze", return_value=["bad analysis"]):
            with self.assertRaisesRegex(ValueError, "no recognized part of speech"):
                lemmatize("word")

    def test_exact_lemma_wins_over_longer_lemma(self):
        with patch.object(lemmatizer, "analyze", return_value=[
            "ometv+V+Present", "+Possessive3+omat+N", "omē+Adj",
        ]):
            self.assertEqual(lemmatize("OMAT"), ["omat"])

    def test_equal_length_lemmas_keep_first_analysis(self):
        with patch.object(lemmatizer, "analyze", return_value=[
            "palen+Num", "other+N",
        ]):
            self.assertEqual(lemmatize("pale"), ["palen"])
        with patch.object(lemmatizer, "analyze", return_value=[
            "abc+N", "aę̄c+N",
        ]):
            self.assertEqual(lemmatize("word"), ["abc"])
