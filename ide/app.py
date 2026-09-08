from __future__ import annotations

import sys
from pathlib import Path

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener
from antlr4.tree.Tree import TerminalNode
from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "program"
for import_path in (ROOT, PROGRAM):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from generated.CompiscriptLexer import CompiscriptLexer
from generated.CompiscriptParser import CompiscriptParser
from semantic.analyzer import SemanticAnalyzer

from ide.demo_cases import DemoCase, DEMO_CASES


class CollectingErrorListener(ErrorListener):
    def __init__(self, category: str):
        super().__init__()
        self.category = category
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, error):
        self.errors.append(
            {
                "line": line,
                "column": column,
                "message": msg,
                "rule": f"error-{self.category}",
                "category": self.category,
            }
        )


def _tree_to_json(node, parser):
    if isinstance(node, TerminalNode):
        return {"kind": "token", "label": node.getText()}
    rule_index = node.getRuleIndex()
    return {
        "kind": "rule",
        "label": parser.ruleNames[rule_index],
        "children": [_tree_to_json(node.getChild(i), parser) for i in range(node.getChildCount())],
    }


def _symbols_to_json(analyzer: SemanticAnalyzer):
    scopes = analyzer.symbol_table.scopes
    scope_ids = {id(scope): index for index, scope in enumerate(scopes)}
    result = []
    for index, scope in enumerate(scopes):
        for symbol in scope.symbols.values():
            result.append(
                {
                    "name": symbol.name,
                    "type": symbol.type.name if symbol.type is not None else "inferido/desconocido",
                    "category": symbol.category.name.lower(),
                    "scope": scope.kind.name.lower(),
                    "scopeId": index,
                    "parentScopeId": scope_ids.get(id(scope.parent)) if scope.parent is not None else None,
                }
            )
    return result


def compile_source(source: str):
    lexer = CompiscriptLexer(InputStream(source))
    lexical_errors = CollectingErrorListener("lexico")
    lexer.removeErrorListeners()
    lexer.addErrorListener(lexical_errors)

    parser = CompiscriptParser(CommonTokenStream(lexer))
    syntax_errors = CollectingErrorListener("sintactico")
    parser.removeErrorListeners()
    parser.addErrorListener(syntax_errors)
    tree = parser.program()

    errors = lexical_errors.errors + syntax_errors.errors
    symbols = []
    if not errors:
        analyzer = SemanticAnalyzer()
        analyzer.visit(tree)
        errors.extend(
            {
                "line": error.line,
                "column": error.column,
                "message": error.message,
                "rule": error.rule,
                "category": "semantico",
            }
            for error in analyzer.errors.errors
        )
        symbols = _symbols_to_json(analyzer)

    return {
        "success": not errors,
        "errors": errors,
        "symbols": symbols,
        "tree": _tree_to_json(tree, parser),
    }


def _demo_case_passed(case: DemoCase, result: dict) -> bool:
    if case.expect_success:
        return result["success"] is True
    if result["success"]:
        return False
    if case.expect_rule is None:
        return True
    return any(error["rule"] == case.expect_rule for error in result["errors"])


def run_demo_suite() -> list[dict]:
    """Compile every case from ide.demo_cases and compare it against what it
    should do, so the IDE can show a live pass/fail run."""
    results = []
    for case in DEMO_CASES:
        result = compile_source(case.source)
        results.append(
            {
                "id": case.id,
                "group": case.group,
                "title": case.title,
                "source": case.source,
                "expectSuccess": case.expect_success,
                "expectRule": case.expect_rule,
                "success": result["success"],
                "errors": result["errors"],
                "passed": _demo_case_passed(case, result),
            }
        )
    return results


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/compile")
    def compile_endpoint():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("source"), str):
            return jsonify({"error": "El cuerpo debe ser JSON con un campo 'source' de tipo string."}), 400
        return jsonify(compile_source(payload["source"]))

    @app.get("/demo-tests")
    def demo_tests_endpoint():
        return jsonify(run_demo_suite())

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
