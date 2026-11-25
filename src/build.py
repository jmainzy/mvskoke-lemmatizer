"""Build an HFST optimized-lookup analyzer from the lexc and twol sources."""

from pathlib import Path
import shutil
import tempfile

import hfst


ROOT = Path(__file__).resolve().parent.parent


def build_analyzer(lexicon_path, morphology_path, phonology_path, output_path):
    lexicon = lexicon_path.read_text(encoding="utf-8")
    morphology = morphology_path.read_text(encoding="utf-8")
    lexicon_header, lexicon_separator, lexicon_body = lexicon.partition("LEXICON ")
    morphology_header, morphology_separator, morphology_body = morphology.partition("LEXICON ")
    if not lexicon_separator or not morphology_separator or "Multichar_Symbols" not in morphology_header:
        raise ValueError("Both lexc files must contain their declarations and lexicons")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_path.parent) as directory:
        directory = Path(directory)
        combined = directory / "combined.lexc"
        combined.write_text(
            lexicon_header + morphology_header.replace("Multichar_Symbols", "", 1)
            + lexicon_separator + lexicon_body + morphology_separator + morphology_body,
            encoding="utf-8",
        )
        transducer = hfst.compile_lexc_file(str(combined))
        if transducer is None:
            raise RuntimeError("Could not compile lexc grammar")

        for source in (phonology_path, phonology_path.with_name("stative.twol"),
                       phonology_path.with_name("person.twol")):
            rules_path = directory / f"{source.stem}.hfst"
            if hfst.compile_twolc_file(str(source), str(rules_path)):
                raise RuntimeError(f"Could not compile two-level rules from {source}")
            stream = hfst.HfstInputStream(str(rules_path))
            rules = []
            try:
                while not stream.is_eof():
                    rules.append(stream.read())
            finally:
                stream.close()
            if not rules:
                raise RuntimeError(f"No two-level rules were compiled from {source}")
            transducer.compose_intersect(tuple(rules))
        transducer.invert()
        transducer.minimize()
        transducer.convert(hfst.ImplementationType.HFST_OL_TYPE)
        built = directory / "analyzer.hfstol"
        output = hfst.HfstOutputStream(filename=str(built), type=hfst.ImplementationType.HFST_OL_TYPE)
        try:
            output.write(transducer)
        finally:
            output.close()
        built.replace(output_path)


def main():
    output = ROOT / "build" / "analyzer.hfstol"
    build_analyzer(ROOT / "grammar" / "lexicon.lexc", ROOT / "grammar" / "morphology.lexc",
                   ROOT / "grammar" / "phonology.twol", output)
    shutil.copyfile(output, ROOT / "src" / "analyzer.hfstol")
    print(f"built {output}")


if __name__ == "__main__":
    main()
