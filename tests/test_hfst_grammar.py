import importlib.util
from pathlib import Path
import tempfile
import unittest

from src.export_lexicon import export_lexicon


ROOT = Path(__file__).resolve().parents[1]
HAS_HFST = importlib.util.find_spec("hfst") is not None


@unittest.skipUnless(HAS_HFST, "requires HFST Python bindings")
class HfstGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import hfst

        cls.tempdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tempdir.cleanup)
        directory = Path(cls.tempdir.name)
        grammar = (ROOT / "src" / "morphology.lexc").read_text(encoding="utf-8")
        # The fixture supplies the lexical roots; the grammar supplies their continuations.
        grammar = grammar.replace("Multichar_Symbols\n", "Multichar_Symbols\n+V +N +Num +Adj\n", 1)
        grammar += """
LEXICON Root
hecetv RegularEntry ;
mēcetv RegularEntry ;
puecetv RegularEntry ;
puetetv RegularEntry ;
voketv RegularEntry ;
hoccetv RegularEntry ;
hosketv RegularEntry ;
hayetv SingularEntry ;
nokose NounEntry ;
nerē DefiniteEntry ;
ocetv DefiniteVerbEntry ;
palen NumeralEntry ;
tayē StativePastEntry ;

LEXICON RegularEntry
+V: RegularVerb ;
LEXICON SingularEntry
+V: SingularVerb ;
LEXICON NounEntry
+N: Nominal ;
LEXICON DefiniteEntry
+N: DefiniteVowel ;
LEXICON DefiniteVerbEntry
+V: DefiniteVerb ;
LEXICON NumeralEntry
+Num: NumeralBase ;
LEXICON StativePastEntry
+Adj: StativePast ;
"""
        lexicon = directory / "fixture.lexc"
        lexicon.write_text(grammar, encoding="utf-8")
        rules = directory / "rules.hfst"
        if hfst.compile_twolc_file(str(ROOT / "src" / "phonology.twol"), str(rules), silent=True):
            raise AssertionError("Could not compile two-level rules")
        transducer = hfst.compile_lexc_file(str(lexicon))
        if transducer is None:
            raise AssertionError("Could not compile lexc grammar")
        stream = hfst.HfstInputStream(str(rules))
        rule_transducers = []
        while not stream.is_eof():
            rule_transducers.append(stream.read())
        stream.close()
        transducer.compose_intersect(tuple(rule_transducers))
        transducer.invert()
        transducer.convert(hfst.ImplementationType.HFST_OL_TYPE)
        cls.analyzer = transducer

    def test_present_and_past_grades(self):
        for surface, analysis in (
            ("hēces", "hecetv+V+Present"),
            ("hehces", "hecetv+V+Past1"),
            ("mehces", "mēcetv+V+Past1"),
            ("puehces", "puecetv+V+Past1"),
            ("puyites", "puetetv+V+Past1"),
            ("vwikes", "voketv+V+Past1"),
            ("hociyes", "hoccetv+V+Past1"),
            ("hosikes", "hosketv+V+Past1"),
        ):
            with self.subTest(surface=surface):
                self.assertIn(analysis, {a for a, _ in self.analyzer.lookup(surface)})

    def test_verb_endings_and_irregular_singular_restriction(self):
        for surface, analysis in (
            ("hoskvntv", "hosketv+V+Past4"),
            ("hoskvtēs", "hosketv+V+Past5"),
            ("hoskvrēs", "hosketv+V+Future"),
            ("hoskvhanes", "hosketv+V+Vhan"),
            ("hosken", "hosketv+V+VerbAdverb"),
            ("hoskeko", "hosketv+V+VerbEko"),
            ("hoske", "hosketv+V+VerbFormE"),
            ("hosket", "hosketv+V+VerbFormEt"),
            ("hosiket", "hosketv+V+PastParticiple"),
            ("hayvkēs", "hayetv+V+Imperative"),
        ):
            with self.subTest(surface=surface):
                self.assertIn(analysis, {a for a, _ in self.analyzer.lookup(surface)})
        self.assertNotIn("hayetv+V+Imperative", {a for a, _ in self.analyzer.lookup("hayvks")})

    def test_nominal_and_numeral_forms(self):
        for surface, analysis in (
            ("nokoset", "nokose+N+Subject"),
            ("nokosen", "nokose+N+DirectObject"),
            ("nerat", "nerē+N+DefiniteSubject"),
            ("ocat", "ocetv+V+DefiniteSubject"),
            ("pale", "palen+Num+NumeralBase"),
            ("tayvtēs", "tayē+Adj+Past5"),
        ):
            with self.subTest(surface=surface):
                self.assertIn(analysis, {a for a, _ in self.analyzer.lookup(surface)})


@unittest.skipUnless(HAS_HFST, "requires HFST Python bindings")
class HfstDictionaryIntegrationTests(unittest.TestCase):
    def test_exported_entries_use_their_verb_classes(self):
        import hfst

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lift = root / "dictionary.lift"
            lift.write_text("""<lift>
<entry id="singular"><lexical-unit><form lang="mus"><text>hayetv</text></form></lexical-unit>
  <relation type="EntryDu" ref="plural"/>
  <sense><grammatical-info value="verb"/></sense></entry>
<entry id="plural"><lexical-unit><form lang="mus"><text>hahicetv</text></form></lexical-unit>
  <sense><grammatical-info value="verb"/></sense></entry>
<entry id="ten"><lexical-unit><form lang="mus"><text>palen</text></form></lexical-unit>
  <sense><grammatical-info value="numeral"/></sense></entry>
</lift>""", encoding="utf-8")
            lexicon = root / "lexicon.lexc"
            export_lexicon(lift, lexicon)
            from src.build import build_analyzer

            analyzer_path = root / "analyzer.hfstol"
            build_analyzer(lexicon, ROOT / "src" / "morphology.lexc",
                           ROOT / "src" / "phonology.twol", analyzer_path)
            stream = hfst.HfstInputStream(str(analyzer_path))
            transducer = stream.read()
            stream.close()
            self.assertIn("hayetv+V", {a for a, _ in transducer.lookup("hayetv")})
            self.assertIn("palen+Num+NumeralBase", {a for a, _ in transducer.lookup("pale")})
            self.assertIn("hayetv+V+Plural+Present", {a for a, _ in transducer.lookup("hahices")})
            self.assertNotIn("hayetv+V+Imperative", {a for a, _ in transducer.lookup("hayvks")})


if __name__ == "__main__":
    unittest.main()
