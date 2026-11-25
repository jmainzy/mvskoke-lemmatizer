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
        grammar = (ROOT / "grammar" / "morphology.lexc").read_text(encoding="utf-8")
        # The fixture supplies the lexical roots; the grammar supplies their continuations.
        grammar = grammar.replace("Multichar_Symbols\n", "Multichar_Symbols\n+V +N +Num +Adj\n", 1)
        header, grammar_body = grammar.split("LEXICON PersonRoot", 1)
        grammar = header + """
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

""" + "LEXICON PersonRoot" + grammar_body + """
LEXICON PersonVerbs
hecetv RegularEntry ;

LEXICON PatientVerbs
hecetv RegularEntry ;

LEXICON ComparisonAdjectives
0:0 # ;

LEXICON PossessiveCvNouns
0:0 # ;
LEXICON PossessiveVmNouns
0:0 # ;
LEXICON PossessiveBoundNouns
0:0 # ;
LEXICON PossessiveProperNouns
0:0 # ;

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
        if hfst.compile_twolc_file(str(ROOT / "grammar" / "phonology.twol"), str(rules), silent=True):
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

    def test_past_third_plural_stem_classes(self):
        for surface, analysis in (
            ("hecvhkes", "hecetv+V+Past1+ThirdPlural"),
            ("puehcakes", "puecetv+V+Past1+ThirdPlural"),
            ("puyitakes", "puetetv+V+Past1+ThirdPlural"),
            ("vwikakes", "voketv+V+Past1+ThirdPlural"),
            ("hociyakes", "hoccetv+V+Past1+ThirdPlural"),
            ("hosikakes", "hosketv+V+Past1+ThirdPlural"),
        ):
            with self.subTest(surface=surface):
                self.assertIn(analysis, {a for a, _ in self.analyzer.lookup(surface)})
        for surface, analysis in (
            ("hehcakes", "hecetv+V+Past1+ThirdPlural"),
            ("puecvhkes", "puecetv+V+Past1+ThirdPlural"),
            ("hayvhkes", "hayetv+V+Past1+ThirdPlural"),
            ("hayhakes", "hayetv+V+Past1+ThirdPlural"),
        ):
            with self.subTest(surface=surface):
                self.assertNotIn(analysis, {a for a, _ in self.analyzer.lookup(surface)})

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
    def test_adverbs_negatives_and_with_forms(self):
        import pyhfst
        from src.build import build_analyzer

        words = {
            "verb": ("hecetv", "esketv", "yvhiketv", "vtotketv", "hompetv",
                     "opvnetv", "vyetv", "akkopvnetv"),
            "adjective": ("cvyayvkē", "herē", "pvfnē", "cvpakkē", "cvpkē", "mahē", "rakkē"),
            "noun": ("nerē", "hvthvyvtke", "yafkat", "ohrolopē", "cuko"),
            "numeral": ("hvmken",),
            "adverb": ("hoyanat",),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lift = root / "dictionary.lift"
            lift.write_text("<lift>" + "".join(
                f'<entry><lexical-unit><form lang="mus"><text>{word}</text></form>'
                f'</lexical-unit><sense><grammatical-info value="{pos}"/></sense></entry>'
                for pos, items in words.items() for word in items
            ) + "</lift>", encoding="utf-8")
            lexicon = root / "lexicon.lexc"
            export_lexicon(lift, lexicon)
            path = root / "analyzer.hfstol"
            build_analyzer(lexicon, ROOT / "grammar" / "morphology.lexc",
                           ROOT / "grammar" / "phonology.twol", path)
            analyzer = pyhfst.HfstInputStream(str(path)).read()

            for surface, analysis in (
                ("cvyayvkēn", "cvyayvkē+Adj+Manner"),
                ("herēn", "herē+Adj+Manner"),
                ("pvfnēn", "pvfnē+Adj+Manner"),
                ("nereyisē", "nerē+N+TimeRecent"),
                ("hvthvyvtkeyisēn", "hvthvyvtke+N+TimeRecent"),
                ("yafkisē", "yafkat+N+TimeRecent"),
                ("ohrolopē-vnkē", "ohrolopē+N+TimeEarlier"),
                ("hvmkvnkē", "hvmken+Num+TimeEarlier"),
                ("hoyanvnkē", "hoyanat+Adv+TimeEarlier"),
                ("hecekos", "hecetv+V+Negative+Agent3+Statement"),
                ("eskvkos", "esketv+V+Negative+Agent1S+Statement"),
                ("eskvks", "esketv+V+Negative+Agent1S+Statement"),
                ("esketskekos", "esketv+V+Negative+Agent2+Statement"),
                ("eskekos", "esketv+V+Negative+Agent3+Statement"),
                ("eskēkos", "esketv+V+Negative+Agent1P+Statement"),
                ("eskatskekos", "esketv+V+Negative+Agent2P+Statement"),
                ("yvhikeko", "yvhiketv+V+Negative+Agent3+Question"),
                ("yvhikeks", "yvhiketv+V+Negative+Agent3+Statement"),
                ("cvpakkekot", "cvpakkē+Adj+Stative+Negative"),
                ("cvcvpakkekot", "cvpakkē+Adj+Stative+First+Negative"),
                ("cecvpakkekot", "cvpakkē+Adj+Stative+Second+Negative"),
                ("pucvpakkekot", "cvpakkē+Adj+Stative+FirstPlural+Negative"),
                ("eshompis", "+Instrumental+hompetv+V+Present"),
                ("’sakkopvnetv", "+Instrumental+akkopvnetv+V"),
                ("escvhēces", "+Instrumental+Patient1S+hecetv+V+Present"),
                ("’svcayes", "+Instrumental+Patient1S+vyetv+V+Present"),
                ("’secēyes", "+Instrumental+Patient2+vyetv+V+Present"),
                ("avm opanes", "+Comitative1S+opvnetv+V+Present"),
                ("iecem opanes", "+Comitative2+opvnetv+V+Present"),
                ("iem opanes", "+Comitative3+opvnetv+V+Present"),
                ("a em opanes", "+Comitative3+opvnetv+V+Present"),
                ("iepum opanes", "+Comitative1P+opvnetv+V+Present"),
                ("avnyvhikes", "+Comitative1S+yvhiketv+V+Present"),
                ("iecenyvhikes", "+Comitative2+yvhiketv+V+Present"),
                ("ienyvhikes", "+Comitative3+yvhiketv+V+Present"),
                ("iepunyvhikes", "+Comitative1P+yvhiketv+V+Present"),
                ("’svm mahēt", "+Compare1S+mahē+Adj+Stative"),
                ("escem mahvyēt", "+Compare2+mahē+Adj+Stative+Agent1S"),
                ("’sem mahvkot", "+Compare3+mahē+Adj+Stative+Agent1S+Negative"),
                ("’sencvpkekot", "+Compare3+cvpkē+Adj+Stative+Negative"),
                ("’senrakketskē", "+Compare3+rakkē+Adj+Stative+Agent2+Question"),
            ):
                with self.subTest(surface=surface):
                    self.assertIn(analysis, {a for a, _ in analyzer.lookup(surface)})
            for surface, analysis in (
                ("hēcekos", "hecetv+V+Negative+Agent3+Statement"),
                ("cukoekos", "cuko+N+Negative+Agent3+Statement"),
                ("escukon", "+Instrumental+cuko+N+DirectObject"),
                ("esakkopvnetv", "+Instrumental+akkopvnetv+V"),
                ("’shompetv", "+Instrumental+hompetv+V"),
                ("hvmkv-isē", "hvmken+Num+TimeRecent"),
                ("cuko-vnkē", "cuko+N+TimeEarlier"),
            ):
                with self.subTest(surface=surface):
                    self.assertNotIn(analysis, {a for a, _ in analyzer.lookup(surface)})

    def test_noun_possessives(self):
        import pyhfst
        from src.build import build_analyzer

        nouns = ("hvcko", "enke", "ēwvnwv", "onvpv", "atvme", "mēkko",
                 "cuko", "poyvfekcv", "enhesse", "empvlse", "faketv",
                 "Hesaketvmesē", "newnoun", "afaka")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lift = root / "dictionary.lift"
            lift.write_text("<lift>" + "".join(
                f'<entry><lexical-unit><form lang="mus"><text>{word}</text></form>'
                '</lexical-unit><sense><grammatical-info value="noun"/></sense></entry>'
                for word in nouns
            ) + '<entry><lexical-unit><form lang="mus"><text>hecetv</text></form>'
                '</lexical-unit><sense><grammatical-info value="verb"/></sense></entry>'
                "</lift>", encoding="utf-8")
            lexicon = root / "lexicon.lexc"
            export_lexicon(lift, lexicon)
            analyzer_path = root / "analyzer.hfstol"
            build_analyzer(lexicon, ROOT / "grammar" / "morphology.lexc",
                           ROOT / "grammar" / "phonology.twol", analyzer_path)
            analyzer = pyhfst.HfstInputStream(str(analyzer_path)).read()

            for surface, analysis in (
                ("cvhvcko", "+Possessive1S+hvcko+N"),
                ("cehvcko", "+Possessive2+hvcko+N"),
                ("ehvcko", "+Possessive3+hvcko+N"),
                ("hvcko", "+Possessive3+hvcko+N"),
                ("puhvcko", "+Possessive1P+hvcko+N"),
                ("cvnke", "+Possessive1S+enke+N"),
                ("cenke", "+Possessive2+enke+N"),
                ("enke", "+Possessive3+enke+N"),
                ("punke", "+Possessive1P+enke+N"),
                ("cawvnwv", "+Possessive1S+ēwvnwv+N"),
                ("cēwvnwv", "+Possessive2+ēwvnwv+N"),
                ("powvnwv", "+Possessive1P+ēwvnwv+N"),
                ("vconvpv", "+Possessive1S+onvpv+N"),
                ("econvpv", "+Possessive2+onvpv+N"),
                ("eponvpv", "+Possessive1P+onvpv+N"),
                ("vcafaka", "+Possessive1S+afaka+N"),
                ("ecafaka", "+Possessive2+afaka+N"),
                ("epafaka", "+Possessive1P+afaka+N"),
                ("vm atvme", "+Possessive1S+atvme+N"),
                ("cem atvme", "+Possessive2+atvme+N"),
                ("em atvme", "+Possessive3+atvme+N"),
                ("pum atvme", "+Possessive1P+atvme+N"),
                ("vm mēkko", "+Possessive1S+mēkko+N"),
                ("vncuko", "+Possessive1S+cuko+N"),
                ("cencuko", "+Possessive2+cuko+N"),
                ("encuko", "+Possessive3+cuko+N"),
                ("puncuko", "+Possessive1P+cuko+N"),
                ("vm poyvfekcv", "+Possessive1S+poyvfekcv+N"),
                ("vnpoyvfekcv", "+Possessive1S+poyvfekcv+N"),
                ("vnhesse", "+Possessive1S+enhesse+N"),
                ("enhesse", "+Possessive3+enhesse+N"),
                ("vmpvlse", "+Possessive1S+empvlse+N"),
                ("vn hesaketvmesē", "+Possessive1S+Hesaketvmesē+N"),
                ("cvnewnoun", "+Possessive1S+newnoun+N"),
                ("vnnewnoun", "+Possessive1S+newnoun+N"),
                ("cvhvckot", "+Possessive1S+hvcko+N+Subject"),
            ):
                with self.subTest(surface=surface):
                    self.assertIn(analysis, {a for a, _ in analyzer.lookup(surface)})

            for surface, analysis in (
                ("vnhvcko", "+Possessive1S+hvcko+N"),
                ("cvcuko", "+Possessive1S+cuko+N"),
                ("vnatvme", "+Possessive1S+atvme+N"),
                ("vnmēkko", "+Possessive1S+mēkko+N"),
                ("vm cuko", "+Possessive1S+cuko+N"),
                ("vnenhesse", "+Possessive1S+enhesse+N"),
                ("cvhecetv", "+Possessive1S+hecetv+V"),
            ):
                with self.subTest(surface=surface):
                    self.assertNotIn(analysis, {a for a, _ in analyzer.lookup(surface)})

    def test_patient_and_dative_person_markers(self):
        import pyhfst
        from src.build import build_analyzer

        words = (
            "hecetv", "enokketv", "vnokecetv", "otvketv", "afvcketv",
            "ēlesketv", "yvhiketv", "cvpakketv", "pohetv", "ohkayetv",
            "opunvyetv", "hompetv", "punvyetv", "nvfketv", "maketv", "emhetv",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lift = root / "dictionary.lift"
            entries = [
                f'<entry id="{word}"><lexical-unit><form lang="mus"><text>{word}</text>'
                '</form></lexical-unit><sense><grammatical-info value="verb"/></sense></entry>'
                for word in words
            ]
            entries.append(
                '<entry id="noun"><lexical-unit><form lang="mus"><text>fakepetv</text>'
                '</form></lexical-unit><sense><grammatical-info value="noun"/></sense></entry>'
            )
            lift.write_text("<lift>" + "".join(entries) + "</lift>", encoding="utf-8")
            lexicon = root / "lexicon.lexc"
            export_lexicon(lift, lexicon)
            analyzer_path = root / "analyzer.hfstol"
            build_analyzer(lexicon, ROOT / "grammar" / "morphology.lexc",
                           ROOT / "grammar" / "phonology.twol", analyzer_path)
            analyzer = pyhfst.HfstInputStream(str(analyzer_path)).read()

            for surface, analysis in (
                ("cvhēces", "+Patient1S+hecetv+V+Present"),
                ("cehēces", "+Patient2+hecetv+V+Present"),
                ("puhēces", "+Patient1P+hecetv+V+Present"),
                ("cvnokkēs", "+Patient1S+enokketv+V+Present"),
                ("cvmhes", "+Patient1S+emhetv+V+Present"),
                ("vcvnokecēs", "+Patient1S+vnokecetv+V+Present"),
                ("ecenokecēs", "+Patient2+vnokecetv+V+Present"),
                ("epunokecēs", "+Patient1P+vnokecetv+V+Present"),
                ("vcotakes", "+Patient1S+otvketv+V+Present"),
                ("ecotakes", "+Patient2+otvketv+V+Present"),
                ("epotakes", "+Patient1P+otvketv+V+Present"),
                ("vcafvckēs", "+Patient1S+afvcketv+V+Present"),
                ("ecēfvckēs", "+Patient2+afvcketv+V+Present"),
                ("epofvckēs", "+Patient1P+afvcketv+V+Present"),
                ("vcaleskēs", "+Patient1S+ēlesketv+V+Present"),
                ("cenafkis", "+Patient2+nvfketv+V+Present"),
                ("vnyvhikes", "+Dative1S+yvhiketv+V+Present"),
                ("cenyvhikes", "+Dative2+yvhiketv+V+Present"),
                ("enyvhikes", "+Dative3+yvhiketv+V+Present"),
                ("punyvhikes", "+Dative1P+yvhiketv+V+Present"),
                ("vm opunayes", "+Dative1S+opunvyetv+V+Present"),
                ("vm makes", "+Dative1S+maketv+V+Present"),
                ("cem pohis", "+Dative2+pohetv+V+Present"),
                ("cencvcvpakkēs", "+Dative2+Patient1S+cvpakketv+V+Present"),
                ("ēhēces", "+PatientReflexive+hecetv+V+Present"),
                ("etehēcēs", "+PatientReciprocal+hecetv+V+Present"),
                ("etohkayetv", "+PatientReciprocal+ohkayetv+V"),
                ("etenhompetv", "+DativeReciprocal+hompetv+V"),
                ("etem punvyetv", "+DativeReciprocal+punvyetv+V"),
            ):
                with self.subTest(surface=surface):
                    self.assertIn(analysis, {a for a, _ in analyzer.lookup(surface)})

            for surface, analysis in (
                ("vnopunayes", "+Dative1S+opunvyetv+V+Present"),
                ("vnmakes", "+Dative1S+maketv+V+Present"),
                ("eteohkayetv", "+PatientReciprocal+ohkayetv+V"),
                ("cvfakepetv", "+Patient1S+fakepetv+N"),
                ("cvheces", "+Patient1S+hecetv+V+Present"),
            ):
                with self.subTest(surface=surface):
                    self.assertNotIn(analysis, {a for a, _ in analyzer.lookup(surface)})

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
            build_analyzer(lexicon, ROOT / "grammar" / "morphology.lexc",
                           ROOT / "grammar" / "phonology.twol", analyzer_path)
            stream = hfst.HfstInputStream(str(analyzer_path))
            transducer = stream.read()
            stream.close()
            self.assertIn("hayetv+V", {a for a, _ in transducer.lookup("hayetv")})
            self.assertIn("palen+Num+NumeralBase", {a for a, _ in transducer.lookup("pale")})
            self.assertIn("hayetv+V+Plural+Present", {a for a, _ in transducer.lookup("hahices")})
            self.assertIn("+Patient1S+hayetv+V+Plural+Present",
                          {a for a, _ in transducer.lookup("cvhahices")})
            self.assertIn("+Dative1S+hayetv+V+Plural+Present",
                          {a for a, _ in transducer.lookup("vnhahices")})
            self.assertIn("hayetv+V+Plural+Past1+ThirdPlural",
                          {a for a, _ in transducer.lookup("hahicvhkes")})
            self.assertNotIn("hayetv+V+Past1+ThirdPlural",
                             {a for a, _ in transducer.lookup("hayvhkes")})
            self.assertNotIn("hayetv+V+Imperative", {a for a, _ in transducer.lookup("hayvks")})

    def test_stative_forms_match_lemmatizer(self):
        import hfst
        from src.build import build_analyzer
        from tests.stative_baseline import stative_derivations, stative_stems

        words = ("atayē", "ētē", "vpayē", "otayē", "etayē", "tayē", "teke", "e", "hvnē", "vcę̄wē")
        tags = ("", "+First", "+Second", "+FirstPlural", "+SecondPlural", "+ThirdPlural")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lift = root / "dictionary.lift"
            entries = []
            for word in words:
                relation = '<relation type="EntryPl" ref="plural"/>' if word == "hvnē" else ""
                entries.append(
                    f'<entry id="{word}"><lexical-unit><form lang="mus"><text>{word}</text>'
                    f'</form></lexical-unit>{relation}<sense><grammatical-info value="adjective"/>'
                    '</sense></entry>'
                )
            lift.write_text("<lift>" + "".join(entries) + "</lift>", encoding="utf-8")
            lexicon = root / "lexicon.lexc"
            export_lexicon(lift, lexicon)
            analyzer_path = root / "analyzer.hfstol"
            build_analyzer(lexicon, ROOT / "grammar" / "morphology.lexc",
                           ROOT / "grammar" / "phonology.twol", analyzer_path)
            stream = hfst.HfstInputStream(str(analyzer_path))
            analyzer = stream.read()
            stream.close()
            import pyhfst

            lookup = pyhfst.HfstInputStream(str(analyzer_path)).read()
            self.assertIn("vcę̄wē+Adj", {a for a, _ in lookup.lookup("vcę̄wē")})
            self.assertIn("teke+Adj+Stative+Derived",
                          {a for a, _ in lookup.lookup("tę̄kusē")})
            for word in words:
                regular = word != "hvnē"
                for stem, person in zip(stative_stems(word, regular), tags):
                    for surface in (stem, stem + "s", stem + "tis", stem + "n"):
                        with self.subTest(word=word, surface=surface, person=person):
                            self.assertIn(f"{word}+Adj+Stative{person}",
                                          {a for a, _ in analyzer.lookup(surface)})
                    for derived in stative_derivations(stem):
                        for surface in (derived, derived + "s", derived + "tis", derived + "n"):
                            with self.subTest(word=word, surface=surface, person=person):
                                self.assertIn(f"{word}+Adj+Stative{person}+Derived",
                                              {a for a, _ in analyzer.lookup(surface)})
                if not regular:
                    for stem, person in zip(stative_stems(word, True)[3:], tags[3:]):
                        with self.subTest(word=word, surface=stem, person=person):
                            self.assertNotIn(f"{word}+Adj+Stative{person}",
                                             {a for a, _ in analyzer.lookup(stem)})
            self.assertNotIn("teke+Adj+Stative", {a for a, _ in analyzer.lookup("tekes")})
            self.assertNotIn("teke+Adj+Stative+Derived",
                             {a for a, _ in analyzer.lookup("tąkusē")})
            self.assertNotIn("vpayē+Adj+Stative", {a for a, _ in analyzer.lookup("payē")})
            analyzer.convert(hfst.ImplementationType.TROPICAL_OPENFST_TYPE)
            analyzer.invert()
            analyzer.convert(hfst.ImplementationType.HFST_OL_TYPE)
            for word, index in (("teke", 0), ("vpayē", 4)):
                stem = stative_stems(word, True)[index]
                expected = {base + ending for base in stative_derivations(stem)
                            for ending in ("", "s", "tis", "n")}
                analysis = f"{word}+Adj+Stative{tags[index]}+Derived"
                with self.subTest(analysis=analysis):
                    self.assertEqual(expected, {surface for surface, _ in analyzer.lookup(analysis)})


if __name__ == "__main__":
    unittest.main()
