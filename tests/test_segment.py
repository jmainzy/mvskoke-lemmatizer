import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.segment import Morphology


LIFT = """<lift>
<entry id="ten">
  <lexical-unit><form lang="mus"><text>palen</text></form></lexical-unit>
  <sense id="ten-sense"><grammatical-info value="numeral"/></sense>
</entry>
<entry id="five">
  <lexical-unit><form lang="mus"><text>cahkēpen</text></form></lexical-unit>
  <sense id="five-sense"><grammatical-info value="numeral"/></sense>
</entry>
<entry id="noun">
  <lexical-unit><form lang="mus"><text>kelen</text></form></lexical-unit>
  <sense id="noun-sense"><grammatical-info value="noun"/></sense>
</entry>
</lift>"""


class NumeralAnalysisTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lexicon = Path(directory.name) / "lexicon.lift"
        lexicon.write_text(LIFT, encoding="utf-8")
        self.analyzer = Morphology(lexicon)

    def test_numeral_base_and_dictionary_form_share_the_entry(self):
        self.assertEqual(self.analyzer.analyze("pale"), ("palen", ["ten"]))
        self.assertEqual(self.analyzer.analyze("palen"), ("palen", ["ten"]))
        self.assertIn("pale", self.analyzer.fst.generate("palen"))
        self.assertEqual(self.analyzer.analyze("cahkepe"), ("cahkēpen", ["five"]))

    def test_does_not_remove_n_from_non_numerals(self):
        self.assertEqual(self.analyzer.analyze("kele"), (None, []))
        self.assertEqual(self.analyzer.analyze("kelen"), ("kelen", ["noun"]))

    def test_free_variants_inherit_entry_ids_without_cycles_or_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            lexicon = Path(directory) / "lexicon.lift"
            lexicon.write_text("""<lift>
<entry id="variant" guid="not-the-id">
  <lexical-unit><form lang="mus"><text>nettv</text></form></lexical-unit>
  <relation type="_component-lexeme" ref="middle">
    <trait name="variant-type" value="Free Variant"/>
  </relation>
  <relation type="_component-lexeme" ref="base">
    <trait name="variant-type" value="Free Variant"/>
  </relation>
  <relation type="_component-lexeme" ref="ignored">
    <trait name="variant-type" value="Short Form"/>
  </relation>
</entry>
<entry id="variant-2">
  <lexical-unit><form lang="mus"><text>nettv</text></form></lexical-unit>
</entry>
<entry id="middle">
  <lexical-unit><form lang="mus"><text>other word</text></form></lexical-unit>
  <relation type="_component-lexeme" ref="base">
    <trait name="variant-type" value="Free Variant"/>
  </relation>
</entry>
<entry id="base">
  <lexical-unit><form lang="mus"><text>netta</text></form></lexical-unit>
  <relation type="_component-lexeme" ref="variant">
    <trait name="variant-type" value="Free Variant"/>
  </relation>
  <relation type="_component-lexeme" ref="last">
    <trait name="variant-type" value="Free Variant"/>
  </relation>
  <sense id="sense"/>
</entry>
<entry id="last"><lexical-unit><form lang="mus"><text>last word</text></form></lexical-unit></entry>
<entry id="ignored"><lexical-unit><form lang="mus"><text>ignore</text></form></lexical-unit></entry>
</lift>""", encoding="utf-8")
            analyzer = Morphology(lexicon)
            self.assertEqual(analyzer.analyze("nettv"), ("nettv", ["variant", "variant-2", "middle", "base", "last"]))
            self.assertEqual(analyzer.analyze("netta"), ("netta", ["base", "variant", "last", "middle"]))

    def test_missing_variant_reference_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            lexicon = Path(directory) / "lexicon.lift"
            lexicon.write_text("""<lift>
<entry id="variant">
  <lexical-unit><form lang="mus"><text>nettv</text></form></lexical-unit>
  <relation type="_component-lexeme" ref="missing">
    <trait name="variant-type" value="Free Variant"/>
  </relation>
</entry></lift>""", encoding="utf-8")
            with self.assertWarnsRegex(UserWarning, "references missing entry"):
                analyzer = Morphology(lexicon)
            self.assertEqual(analyzer.analyze("nettv"), ("nettv", ["variant"]))

    def test_missing_and_duplicate_entry_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            lexicon = Path(directory) / "lexicon.lift"
            lexicon.write_text('<lift><entry/></lift>', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing entry id"):
                Morphology(lexicon)
            lexicon.write_text('<lift><entry id="same"/><entry id="same"/></lift>', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate entry id"):
                Morphology(lexicon)


class VowelMatchingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lexicon = Path(directory.name) / "lexicon.lift"
        lexicon.write_text("""<lift>
<entry id="two-edits">
  <lexical-unit><form lang="mus"><text>ponattv</text></form></lexical-unit>
  <sense id="first"/>
</entry>
<entry id="one-edit">
  <lexical-unit><form lang="mus"><text>ponvttv</text></form></lexical-unit>
  <sense id="second"/>
</entry>
<entry id="exact">
  <lexical-unit><form lang="mus"><text>cava</text></form></lexical-unit>
</entry>
<entry id="near-exact">
  <lexical-unit><form lang="mus"><text>caaa</text></form></lexical-unit>
</entry>
<entry id="accented">
  <lexical-unit><form lang="mus"><text>hē</text></form></lexical-unit>
</entry>
<entry id="verb">
  <lexical-unit><form lang="mus"><text>ponetv</text></form></lexical-unit>
  <sense id="verb-sense"><grammatical-info value="verb"/></sense>
</entry>
<entry id="multi">
  <lexical-unit><form lang="mus"><text>folos</text></form></lexical-unit>
</entry>
</lift>""", encoding="utf-8")
        self.analyzer = Morphology(lexicon)

    def test_prefers_fewer_vowel_substitutions(self):
        self.assertEqual(self.analyzer.analyze("Punvttv"), ("ponvttv", ["one-edit"]))
        self.assertEqual(self.analyzer.analyze("fulus"), ("folos", ["multi"]))
        self.assertEqual(self.analyzer.analyze("ponvtta"), ("ponvttv", ["one-edit"]))

    def test_exact_and_accent_insensitive_matches_take_priority(self):
        self.assertEqual(self.analyzer.analyze("cava"), ("cava", ["exact"]))
        self.assertEqual(self.analyzer.analyze("he"), ("hē", ["accented"]))

    def test_vowel_substitution_applies_to_inflected_forms(self):
        self.assertEqual(self.analyzer.analyze("punis"), ("ponetv", ["verb"]))

    def test_other_edits_do_not_match(self):
        self.assertEqual(self.analyzer.analyze("punxttv"), (None, []))
        self.assertEqual(self.analyzer.analyze("ponvtt"), (None, []))
        self.assertEqual(self.analyzer.analyze("ponvttvv"), (None, []))


class TogetherPhraseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.lexicon = Path(directory.name) / "lexicon.lift"
        self.lexicon.write_text("""<lift>
<entry id="together">
  <lexical-unit><form lang="mus"><text>etem punahoyetv</text></form></lexical-unit>
  <relation type="_component-lexeme" ref="component">
    <trait name="complex-form-type" value="Derived form"/>
  </relation>
</entry>
<entry id="component"><lexical-unit><form lang="mus"><text>opunahoyetv</text></form></lexical-unit></entry>
<entry id="another"><lexical-unit><form lang="mus"><text>etem maketv</text></form></lexical-unit></entry>
<entry id="unrelated"><lexical-unit><form lang="mus"><text>other maketv</text></form></lexical-unit></entry>
<entry id="long-phrase"><lexical-unit><form lang="mus"><text>etem other maketv</text></form></lexical-unit></entry>
</lift>""", encoding="utf-8")
        self.analyzer = Morphology(self.lexicon)

    def test_joined_and_inflected_phrases_preserve_the_phrase_entry_id(self):
        for surface in ("etempunahoye", "Etemponahoye", "etemponahoyet"):
            with self.subTest(surface=surface):
                self.assertEqual(self.analyzer.analyze(surface), ("etem punahoyetv", ["together"]))
        self.assertIn("etempunahoye", self.analyzer.fst.generate("etem punahoyetv"))
        self.assertEqual(self.analyzer.analyze("etemmakes"), ("etem maketv", ["another"]))

    def test_exact_entries_win_and_unrelated_phrases_are_not_joined(self):
        self.assertEqual(self.analyzer.analyze("othermaketv"), (None, []))
        self.assertEqual(self.analyzer.analyze("etemothermaketv"), (None, []))
        exact = '<entry id="exact"><lexical-unit><form lang="mus"><text>etemponahoyetv</text></form></lexical-unit></entry>'
        contents = self.lexicon.read_text(encoding="utf-8")
        self.lexicon.write_text(contents.replace("</lift>", exact + "</lift>"), encoding="utf-8")
        analyzer = Morphology(self.lexicon)
        self.assertEqual(analyzer.analyze("etemponahoyetv"), ("etemponahoyetv", ["exact"]))
        self.assertEqual(analyzer.analyze("Etemponahoye"), ("etemponahoyetv", ["exact"]))


class SubjectAndContractionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lexicon = Path(directory.name) / "lexicon.lift"
        lexicon.write_text("""<lift>
<entry id="bear"><lexical-unit><form lang="mus"><text>nokose</text></form></lexical-unit></entry>
<entry id="one"><lexical-unit><form lang="mus"><text>nerē</text></form></lexical-unit></entry>
<entry id="word"><lexical-unit><form lang="mus"><text>sapsvwē</text></form></lexical-unit></entry>
<entry id="verb"><lexical-unit><form lang="mus"><text>ocetv</text></form></lexical-unit></entry>
<entry id="red"><lexical-unit><form lang="mus"><text>lvstē</text></form></lexical-unit></entry>
<entry id="whole"><lexical-unit><form lang="mus"><text>etepakat</text></form></lexical-unit></entry>
<entry id="contracted-noun"><lexical-unit><form lang="mus"><text>eme</text></form></lexical-unit></entry>
</lift>""", encoding="utf-8")
        self.analyzer = Morphology(lexicon)

    def test_subject_t_and_definite_subject_at(self):
        for surface, lemma, entry_id in (
            ("Nokoset", "nokose", "bear"),
            ("Neret", "nerē", "one"),
            ("sapsvwēt", "sapsvwē", "word"),
            ("ocat", "ocetv", "verb"),
            ("lvstat", "lvstē", "red"),
        ):
            with self.subTest(surface=surface):
                self.assertEqual(self.analyzer.analyze(surface), (lemma, [entry_id]))
                self.assertIn(surface.lower(), self.analyzer.fst.generate(lemma))

    def test_initial_e_contraction_with_subject_forms(self):
        for surface in ("tepakat", "'tepakat", "’tepakat"):
            self.assertEqual(self.analyzer.analyze(surface), ("etepakat", ["whole"]))
            self.assertIn(surface, self.analyzer.fst.generate("etepakat"))
        self.assertEqual(self.analyzer.analyze("met"), ("eme", ["contracted-noun"]))
        self.assertEqual(self.analyzer.analyze("mat"), ("eme", ["contracted-noun"]))

    def test_existing_uncontracted_analysis_takes_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            lexicon = Path(directory) / "lexicon.lift"
            lexicon.write_text("""<lift>
<entry id="whole"><lexical-unit><form lang="mus"><text>etepakat</text></form></lexical-unit>
  <sense id="first"/></entry>
<entry id="other"><lexical-unit><form lang="mus"><text>tepake</text></form></lexical-unit>
  <sense id="second"/></entry>
</lift>""", encoding="utf-8")
            self.assertEqual(Morphology(lexicon).analyze("tepakat"), ("tepake", ["other"]))


class AdditionalMorphologyTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lexicon = Path(directory.name) / "lexicon.lift"
        lexicon.write_text("""<lift>
<entry id="hosk"><lexical-unit><form lang="mus"><text>hosketv</text></form></lexical-unit></entry>
<entry id="mec"><lexical-unit><form lang="mus"><text>mēcetv</text></form></lexical-unit></entry>
<entry id="nvkvft"><lexical-unit><form lang="mus"><text>nvkvftetv</text></form></lexical-unit></entry>
<entry id="satkv"><lexical-unit><form lang="mus"><text>satkv</text></form></lexical-unit></entry>
<entry id="eyac"><lexical-unit><form lang="mus"><text>eyacetv</text></form></lexical-unit></entry>
<entry id="mak"><lexical-unit><form lang="mus"><text>maketv</text></form></lexical-unit></entry>
<entry id="hak"><lexical-unit><form lang="mus"><text>haketv</text></form></lexical-unit></entry>
<entry id="etekvpic"><lexical-unit><form lang="mus"><text>etekvpicetv</text></form></lexical-unit></entry>
<entry id="twelve"><lexical-unit><form lang="mus"><text>tuccenohkaken</text></form></lexical-unit></entry>
<entry id="single-c"><lexical-unit><form lang="mus"><text>acoke</text></form></lexical-unit></entry>
<entry id="written-f"><lexical-unit><form lang="mus"><text>pofoko</text></form></lexical-unit></entry>
</lift>""", encoding="utf-8")
        self.analyzer = Morphology(lexicon)

    def test_past_four_and_five_with_prefix_and_vowel_alternation(self):
        for surface, lemma, entry_id in (
            ("hoskvntv", "hosketv", "hosk"),
            ("enhoskvntvs", "hosketv", "hosk"),
            ("enhoskvtēs", "hosketv", "hosk"),
            ("mecakvtēs", "mēcetv", "mec"),
            ("nvkaftvtēs", "nvkvftetv", "nvkvft"),
        ):
            with self.subTest(surface=surface):
                self.assertEqual(self.analyzer.analyze(surface), (lemma, [entry_id]))
        self.assertIn("hoskvntvs", self.analyzer.fst.generate("hosketv"))
        self.assertIn("enhoskvtēs", self.analyzer.fst.generate("hosketv"))
        self.assertEqual(self.analyzer.analyze("enhoskes"), ("hosketv", ["hosk"]))

    def test_direct_object_adverbs_and_split_verb(self):
        for surface, lemma, entry_id in (
            ("satkvn", "satkv", "satkv"),
            ("yacaken", "eyacetv", "eyac"),
            ("maken", "maketv", "mak"),
            ("hakēn", "haketv", "hak"),
            ("etekvpice", "etekvpicetv", "etekvpic"),
        ):
            with self.subTest(surface=surface):
                self.assertEqual(self.analyzer.analyze(surface), (lemma, [entry_id]))
                self.assertIn(surface, self.analyzer.fst.generate(lemma))

    def test_pronunciation_and_single_double_c(self):
        for surface in ("tucenohkaken", "tuccenofkaken", "tucenofkaken"):
            self.assertEqual(self.analyzer.analyze(surface), ("tuccenohkaken", ["twelve"]))
        self.assertEqual(self.analyzer.analyze("accoke"), ("acoke", ["single-c"]))
        self.assertEqual(self.analyzer.analyze("tucccenofkaken"), (None, []))
        self.assertEqual(self.analyzer.analyze("pohoko"), (None, []))


class PossessiveAndStativeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.lexicon = Path(directory.name) / "lexicon.lift"
        self.lexicon.write_text("""<lift>
<entry id="tay"><lexical-unit><form lang="mus"><text>tayē</text></form></lexical-unit></entry>
<entry id="tvlk"><lexical-unit><form lang="mus"><text>tvlkē</text></form></lexical-unit>
  <sense id="tvlk-sense"><grammatical-info value="adjective"/></sense></entry>
<entry id="bear"><lexical-unit><form lang="mus"><text>nokose</text></form></lexical-unit>
  <sense id="bear-sense"><grammatical-info value="noun"/></sense></entry>
<entry id="hop"><lexical-unit><form lang="mus"><text>hoporrenkv</text></form></lexical-unit></entry>
<entry id="em"><lexical-unit><form lang="mus"><text>em</text></form></lexical-unit></entry>
<entry id="apohic"><lexical-unit><form lang="mus"><text>apohicetv</text></form></lexical-unit>
  <sense id="apohic-sense"><grammatical-info value="verb"/></sense></entry>
<entry id="enhomec"><lexical-unit><form lang="mus"><text>enhomecetv</text></form></lexical-unit>
  <sense id="enhomec-sense"><grammatical-info value="verb"/></sense></entry>
</lift>""", encoding="utf-8")
        self.analyzer = Morphology(self.lexicon)

    def test_commas_are_stripped_from_cli_words(self):
        self.assertEqual(self.analyzer.analyze("tayen,"), ("tayē", ["tay"]))
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().with_name("segment.py")),
             "--lexicon", str(self.lexicon), "tayen,", ","],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([json.loads(line) for line in result.stdout.splitlines()],
                         [{"word": "tayen", "stem": "tayē", "ids": ["tay"]}])

    def test_possessive_diminutive_and_stative_past(self):
        for surface, lemma, entry_id in (
            ("enhoporrenkv", "hoporrenkv", "hop"),
            ("tvlkosen", "tvlkē", "tvlk"),
            ("tayvtēs", "tayē", "tay"),
            ("enhomehcet", "enhomecetv", "enhomec"),
        ):
            with self.subTest(surface=surface):
                self.assertEqual(self.analyzer.analyze(surface), (lemma, [entry_id]))
        for surface, lemma in (("enhoporrenkv", "hoporrenkv"), ("tvlkosen", "tvlkē"), ("tayvtēs", "tayē"), ("enhomehcet", "enhomecetv")):
            self.assertIn(surface, self.analyzer.fst.generate(lemma))
        self.assertEqual(self.analyzer.analyze("nokosvtēs"), (None, []))

    def test_combined_em_and_elided_form_include_both_entries(self):
        expected = ("em apohiceko", ["em", "apohic"])
        self.assertEqual(self.analyzer.analyze("emapohiceko"), expected)
        self.assertEqual(self.analyzer.analyze("mapohiceko"), expected)
        self.assertEqual(self.analyzer.analyze("mnokose"), (None, []))

    def test_exact_headword_takes_priority_over_possessive_split(self):
        extra = '<entry id="direct"><lexical-unit><form lang="mus"><text>enhoporrenkv</text></form></lexical-unit></entry>'
        self.lexicon.write_text(self.lexicon.read_text(encoding="utf-8").replace("</lift>", extra + "</lift>"), encoding="utf-8")
        self.assertEqual(Morphology(self.lexicon).analyze("enhoporrenkv"), ("enhoporrenkv", ["direct"]))


class ImperativeAdverbPossessiveTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        lexicon = Path(directory.name) / "lexicon.lift"
        lexicon.write_text("""<lift>
<entry id="hay"><lexical-unit><form lang="mus"><text>hayetv</text></form></lexical-unit>
  <relation type="EntryPl" ref="plural"/></entry>
<entry id="plural"><lexical-unit><form lang="mus"><text>hahicetv</text></form></lexical-unit></entry>
<entry id="hec"><lexical-unit><form lang="mus"><text>hecetv</text></form></lexical-unit></entry>
<entry id="vhec"><lexical-unit><form lang="mus"><text>vhecetv</text></form></lexical-unit></entry>
</lift>""", encoding="utf-8")
        self.analyzer = Morphology(lexicon)

    def test_irregular_imperative_allows_only_the_requested_ending(self):
        self.assertEqual(self.analyzer.analyze("hayvkēs"), ("hayetv", ["hay"]))
        self.assertIn("hayvkēs", self.analyzer.fst.generate("hayetv"))
        self.assertEqual(self.analyzer.analyze("hayvks"), (None, []))
        self.assertEqual(self.analyzer.analyze("hayvkēts"), (None, []))

    def test_present_adverb_uses_n_instead_of_final_s(self):
        for surface in ("hēceccen", "hēcēn", "hēcin"):
            with self.subTest(surface=surface):
                self.assertEqual(self.analyzer.analyze(surface), ("hecetv", ["hec"]))
                self.assertIn(surface, self.analyzer.fst.generate("hecetv"))
        self.assertEqual(self.analyzer.analyze("hayatsken"), (None, []))

    def test_possessive_prefixes_compose_with_verb_forms(self):
        for prefix in ("en", "pum", "cem", "pom", "cen", "vm", "vn", "vc", "cv", "ec"):
            with self.subTest(prefix=prefix):
                self.assertEqual(self.analyzer.analyze(prefix + "vhēcet"), ("vhecetv", ["vhec"]))
                self.assertIn(prefix + "vhecet", self.analyzer.fst.generate("vhecetv"))
        self.assertEqual(self.analyzer.analyze("pumhēceccen"), ("hecetv", ["hec"]))


class StoryScriptTests(unittest.TestCase):
    def test_replaces_output_only_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activation = root / ".venv" / "bin" / "activate"
            activation.parent.mkdir(parents=True)
            activation.write_text("", encoding="utf-8")
            (root / "segment.py").write_text(
                'import sys\n'
                'if "fail" in sys.argv:\n'
                '    raise SystemExit(1)\n'
                'print("\\n".join(sys.argv[1:]))\n',
                encoding="utf-8",
            )
            text = root / "example.txt"
            output = root / "example.json"
            text.write_text("Punvttv ponvttv", encoding="utf-8")
            output.write_text("old output\n", encoding="utf-8")
            command = ["bash", str(Path(__file__).resolve().with_name("index_story.sh"))]
            for _ in range(2):
                result = subprocess.run(command, cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output.read_text(encoding="utf-8"), "Punvttv\nponvttv\n")
            text.write_text("fail", encoding="utf-8")
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "Punvttv\nponvttv\n")


if __name__ == "__main__":
    unittest.main()
