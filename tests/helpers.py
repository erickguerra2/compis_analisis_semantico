from __future__ import annotations

from dataclasses import dataclass

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from generated.CompiscriptLexer import CompiscriptLexer
from generated.CompiscriptParser import CompiscriptParser
from codegen.generator import TacGenerator
from semantic.analyzer import SemanticAnalyzer


class _Errors(ErrorListener):
    def __init__(self):
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, error):
        self.errors.append((line, column, msg))


@dataclass
class CompileResult:
    errors: list
    tac: list[str]
    emitter: object = None
    analyzer: object = None
    tree: object = None


def compile_source(source: str) -> CompileResult:
    listener = _Errors()
    lexer = CompiscriptLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(listener)
    parser = CompiscriptParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(listener)
    tree = parser.program()
    if listener.errors:
        return CompileResult(listener.errors, [], tree=tree)
    analyzer = SemanticAnalyzer()
    analyzer.visit(tree)
    if analyzer.errors.has_errors():
        return CompileResult(list(analyzer.errors.errors), [], analyzer=analyzer, tree=tree)
    emitter = TacGenerator(analyzer, tree).generate()
    return CompileResult([], emitter.lines(), emitter, analyzer, tree)
