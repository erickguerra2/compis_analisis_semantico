from __future__ import annotations

import sys
from pathlib import Path

from antlr4 import CommonTokenStream, FileStream

ROOT = Path(__file__).resolve().parents[1]
for import_path in (ROOT, ROOT / "program"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from generated.CompiscriptLexer import CompiscriptLexer
from generated.CompiscriptParser import CompiscriptParser
from codegen.generator import TacGenerator
from semantic.analyzer import SemanticAnalyzer

def main(argv):
    if len(argv) != 2:
        raise SystemExit("uso: python program/Driver.py archivo.cps")
    input_stream = FileStream(argv[1])
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    tree = parser.program()
    if parser.getNumberOfSyntaxErrors():
        raise SystemExit(1)
    analyzer = SemanticAnalyzer()
    analyzer.visit(tree)
    if analyzer.errors.has_errors():
        for error in analyzer.errors.errors:
            print(f"{error.line}:{error.column}: {error.rule}: {error.message}", file=sys.stderr)
        raise SystemExit(1)
    print(TacGenerator(analyzer, tree).generate().dump())

if __name__ == "__main__":
    main(sys.argv)
