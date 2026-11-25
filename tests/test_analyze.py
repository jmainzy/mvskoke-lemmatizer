import csv
import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

analyze = importlib.import_module("src.analyze")


class AnalyzeFileTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.text = self.root / "story.txt"
        self.output = self.root / "analysis.tsv"
        self.analyzer = self.root / "analyzer.hfstol"

    def test_writes_analyses_for_each_word(self):
        self.text.write_text("pale, hēces\nunknown pale ,\n", encoding="utf-8")
        lookups = {
            "pale": [("palen+Num+NumeralBase", 0.0)],
            "hēces": [("hecetv+V+Present", 0.0), ("Hecetv+Unknown+Present", 1.0)],
            "unknown": [],
        }
        with patch("src.analyze.pyhfst.HfstInputStream") as stream:
            stream.return_value.read.return_value.lookup.side_effect = lambda word: lookups.get(word, [])
            with patch("sys.argv", ["analyze.py", str(self.text), "--output", str(self.output),
                                    "--analyzer", str(self.analyzer)]):
                analyze.main()
        stream.assert_called_once_with(str(self.analyzer))
        with self.output.open(encoding="utf-8", newline="") as result:
            self.assertEqual(list(csv.reader(result, delimiter="\t")), [
                ["word", "analysis"],
                ["pale", "['palen+Num+NumeralBase']"],
                ["hēces", "['hecetv+V+Present', 'Hecetv+Unknown+Present']"],
                ["unknown", "[]"],
                ["pale", "['palen+Num+NumeralBase']"],
            ])

    def test_spaced_dative_adds_a_row_without_losing_words_or_crossing_boundaries(self):
        self.text.write_text(
            "vm opunayes, vm, opunayes\nvm\nopunayes vm opunayes\n",
            encoding="utf-8",
        )
        lookups = {
            "vm": [("vm+Unknown", 0.0)],
            "opunayes": [("opunvyetv+V+Present", 0.0)],
            "vm opunayes": [("+Dative1S+opunvyetv+V+Present", 0.0)],
        }
        with patch("src.analyze.pyhfst.HfstInputStream") as stream:
            stream.return_value.read.return_value.lookup.side_effect = lambda word: lookups.get(word, [])
            with patch("sys.argv", ["analyze.py", str(self.text), "--output", str(self.output),
                                    "--analyzer", str(self.analyzer)]):
                analyze.main()
        with self.output.open(encoding="utf-8", newline="") as result:
            rows = list(csv.DictReader(result, delimiter="\t"))
        self.assertEqual([row["word"] for row in rows], [
            "vm", "vm opunayes", "opunayes", "vm", "opunayes",
            "vm", "opunayes", "vm", "vm opunayes", "opunayes",
        ])
        self.assertEqual(rows[1]["analysis"], "['+Dative1S+opunvyetv+V+Present']")

    def test_spaced_possessive_adds_a_phrase_row(self):
        lookups = {
            "vm efv": [("+Possessive1S+efv+N", 0.0)],
            "vm": [("vm+Unknown", 0.0)],
            "efv": [("efv+N", 0.0)],
        }
        from unittest.mock import Mock

        transducer = Mock()
        transducer.lookup.side_effect = lambda word: lookups.get(word, [])
        self.assertEqual(analyze.analyze_lines([["vm", "efv"]], transducer), [
            ("vm", ["vm+Unknown"]),
            ("vm efv", ["+Possessive1S+efv+N"]),
            ("efv", ["efv+N"]),
        ])

    def test_comitative_and_comparison_phrases_and_question_punctuation(self):
        lookups = {
            "a em opanes": [("+Comitative3+opvnetv+V+Present", 0.0)],
            "’svm mahēt": [("+Compare1S+mahē+Adj+Stative", 0.0)],
            "yvhikeko": [("yvhiketv+V+Negative+Agent3+Question", 0.0)],
        }
        from unittest.mock import Mock

        transducer = Mock()
        transducer.lookup.side_effect = lambda word: lookups.get(word, [])
        results = analyze.analyze_lines([
            ["a", "em", "opanes", "’svm", "mahēt", "yvhikeko?"],
            ["a", "em,", "opanes", "’svm,", "mahēt"],
        ], transducer)
        phrases = [word for word, _ in results if " " in word]
        self.assertEqual(phrases, ["a em opanes", "’svm mahēt"])
        self.assertIn(("yvhikeko", ["yvhiketv+V+Negative+Agent3+Question"]), results)

    def test_refuses_to_overwrite_input_or_analyzer(self):
        self.text.write_text("pale", encoding="utf-8")
        for protected in (self.text, self.analyzer):
            with self.subTest(protected=protected):
                with patch("src.analyze.pyhfst.HfstInputStream") as stream:
                    with patch("sys.argv", ["analyze.py", str(self.text), "--output", str(protected),
                                            "--analyzer", str(self.analyzer)]):
                        with self.assertRaises(SystemExit) as result:
                            analyze.main()
                self.assertEqual(result.exception.code, 2)
                stream.assert_not_called()
        self.assertEqual(self.text.read_text(encoding="utf-8"), "pale")

    def test_refuses_to_overwrite_input_through_hard_link(self):
        self.text.write_text("pale", encoding="utf-8")
        os.link(self.text, self.output)
        with patch("sys.argv", ["analyze.py", str(self.text), "--output", str(self.output)]):
            with self.assertRaises(SystemExit) as result:
                analyze.main()
        self.assertEqual(result.exception.code, 2)
        self.assertEqual(self.text.read_text(encoding="utf-8"), "pale")

    def test_missing_input_or_analyzer_does_not_create_output(self):
        for missing_input in (True, False):
            with self.subTest(missing_input=missing_input):
                if not missing_input:
                    self.text.write_text("pale", encoding="utf-8")
                with patch("sys.argv", ["analyze.py", str(self.text), "--output", str(self.output),
                                        "--analyzer", str(self.analyzer)]):
                    with self.assertRaises(FileNotFoundError):
                        analyze.main()
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
