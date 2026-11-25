import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src import analyze


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
            stream.return_value.read.return_value.lookup.side_effect = lookups.__getitem__
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
