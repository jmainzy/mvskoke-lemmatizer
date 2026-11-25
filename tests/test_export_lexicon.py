import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from src.export_lexicon import export_lexicon


class ExportLexiconTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.lift = Path(directory.name) / "dictionary.lift"
        self.output = Path(directory.name) / "lexicon.lexc"

    def test_headwords_are_normalized_deduplicated_and_escaped(self):
        self.lift.write_text("""<lift>
<entry id="1"><lexical-unit><form lang="mus"><text>cahkēpen</text></form></lexical-unit></entry>
<entry id="2"><lexical-unit><form lang="mus"><text>cahkēpen</text></form></lexical-unit></entry>
<entry id="3"><lexical-unit><form lang="mus"><text>etem maketv</text></form></lexical-unit></entry>
<entry id="4"><lexical-unit><form lang="mus"><text>mą!</text></form></lexical-unit></entry>
<entry id="5"><lexical-unit><form lang="mus"><text>a0%:;#&lt;&gt;"</text></form></lexical-unit></entry>
<entry id="6"><lexical-unit><form lang="en"><text>not Mvskoke</text></form></lexical-unit></entry>
<entry id="7"><lexical-unit><form lang="mus"><text>  </text></form></lexical-unit></entry>
</lift>""", encoding="utf-8")
        self.assertEqual(export_lexicon(self.lift, self.output), (4, 2))
        result = self.output.read_text(encoding="utf-8")
        for line in (
            'a%0%%%:%;%#%<%>%" UncategorizedTag ;',
            "cahkēpen UncategorizedTag ;",
            "etem% maketv UncategorizedTag ;",
            "mą%! UncategorizedTag ;",
        ):
            self.assertEqual(result.count(line), 1)
        self.assertIn("LEXICON UncategorizedTag\n+Unknown: # ;", result)

    def test_verb_class_and_linked_plural_are_exported(self):
        self.lift.write_text("""<lift>
<entry id="singular"><lexical-unit><form lang="mus"><text>hayetv</text></form></lexical-unit>
  <relation type="EntryDu" ref="plural"/>
  <sense><grammatical-info value="verb"/></sense></entry>
<entry id="plural"><lexical-unit><form lang="mus"><text>hahicetv</text></form></lexical-unit>
  <sense><grammatical-info value="verb"/></sense></entry>
</lift>""", encoding="utf-8")
        export_lexicon(self.lift, self.output)
        result = self.output.read_text(encoding="utf-8")
        self.assertIn("hayetv:hayetv VerbsSingularVerbTag ;", result)
        self.assertIn("hayetv:hahicetv VerbsPluralVerbTag ;", result)
        self.assertIn("hahicetv:hahicetv VerbsRegularVerbTag ;", result)
        self.assertIn("+V: PluralVerb ;", result)

    def test_sense_categories_and_uncategorized_entries_are_preserved(self):
        self.lift.write_text("""<lift>
<entry><lexical-unit><form lang="mus"><text>word</text></form></lexical-unit>
  <sense><grammatical-info value="noun"/></sense>
  <sense><grammatical-info value="verb"/></sense>
  <sense/>
</entry>
<entry><lexical-unit><form lang="mus"><text>word</text></form></lexical-unit>
  <sense><grammatical-info value="noun"/></sense>
</entry>
<entry><lexical-unit><form lang="mus"><text>other</text></form></lexical-unit>
  <sense><grammatical-info value="adjective"/></sense>
  <sense><grammatical-info value="adverb"/></sense>
  <sense><grammatical-info value="adjectival noun"/></sense>
</entry>
<entry><lexical-unit><form lang="mus"><text>verb</text></form></lexical-unit>
  <sense><grammatical-info value="v."/></sense>
</entry>
</lift>""", encoding="utf-8")
        self.assertEqual(export_lexicon(self.lift, self.output), (3, 0))
        result = self.output.read_text(encoding="utf-8")
        for lexicon, tag in (
            ("Nouns", "+N"), ("Verbs", "+V"), ("Adjectives", "+Adj"),
            ("Adverbs", "+Adv"), ("AdjectivalNouns", "+AdjN"),
            ("Uncategorized", "+Unknown"),
        ):
            with self.subTest(lexicon=lexicon):
                self.assertIn(f"LEXICON {lexicon}\n", result)
                self.assertIn(f"LEXICON {lexicon}Tag\n{tag}: # ;\n", result)
        self.assertEqual(result.count("word NounsTag ;"), 1)
        self.assertIn("word VerbsTag ;", result)
        self.assertIn("word UncategorizedTag ;", result)
        self.assertIn("verb VerbsTag ;", result)

    def test_unrecognized_category_does_not_replace_output(self):
        self.output.write_text("existing", encoding="utf-8")
        self.lift.write_text(
            '<lift><entry><lexical-unit><form lang="mus"><text>word</text></form>'
            '</lexical-unit><sense><grammatical-info value="new category"/></sense>'
            '</entry></lift>', encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "unknown part of speech 'new category' for 'word'"):
            export_lexicon(self.lift, self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "existing")

    def test_invalid_input_does_not_replace_existing_output(self):
        self.output.write_text("existing", encoding="utf-8")
        for contents in ("<lift><entry>", "<lift/>", "<lift><entry><lexical-unit>"
                         '<form lang="mus"><text>a&#10;b</text></form>'
                         "</lexical-unit></entry></lift>"):
            with self.subTest(contents=contents):
                self.lift.write_text(contents, encoding="utf-8")
                with self.assertRaises((ValueError, ET.ParseError)):
                    export_lexicon(self.lift, self.output)
                self.assertEqual(self.output.read_text(encoding="utf-8"), "existing")

    def test_input_cannot_be_overwritten(self):
        self.lift.write_text("<lift/>", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different files"):
            export_lexicon(self.lift, self.lift)
        self.assertEqual(self.lift.read_text(encoding="utf-8"), "<lift/>")

    def test_cli_writes_requested_output(self):
        self.lift.write_text(
            '<lift><entry><lexical-unit><form lang="mus"><text>palen</text>'
            "</form></lexical-unit></entry></lift>", encoding="utf-8"
        )
        script = Path(__file__).resolve().parents[1] / "src" / "export_lexicon.py"
        result = subprocess.run(
            [sys.executable, str(script), "--lift", str(self.lift), "--output", str(self.output)],
            capture_output=True, text=True, check=True,
        )
        self.assertIn("Exported 1 distinct headwords", result.stdout)
        self.assertIn("palen UncategorizedTag ;", self.output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
