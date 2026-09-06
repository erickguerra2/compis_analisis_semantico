from antlr4 import CommonTokenStream, InputStream

from generated.CompiscriptLexer import CompiscriptLexer
from generated.CompiscriptParser import CompiscriptParser
from semantic.analyzer import SemanticAnalyzer


def _analyze(source: str) -> SemanticAnalyzer:
    lexer = CompiscriptLexer(InputStream(source))
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    tree = parser.program()

    analyzer = SemanticAnalyzer()
    analyzer.visit(tree)
    return analyzer


def _rules(analyzer: SemanticAnalyzer):
    return [error.rule for error in analyzer.errors.errors]


def test_arithmetic_between_integers_is_valid():
    analyzer = _analyze("let x: integer = 1 + 2 * 3;")

    assert not analyzer.errors.has_errors()


def test_arithmetic_with_boolean_operand_is_reported():
    analyzer = _analyze("let x: integer = 1 + true;")

    assert "operador-aritmetico-tipo-invalido" in _rules(analyzer)


def test_logical_operator_requires_boolean_operands():
    analyzer = _analyze("let x: boolean = 1 && true;")

    assert "operador-logico-tipo-invalido" in _rules(analyzer)


def test_logical_operator_with_booleans_is_valid():
    analyzer = _analyze("let x: boolean = true && false || true;")

    assert not analyzer.errors.has_errors()


def test_relational_operator_requires_numeric_operands():
    analyzer = _analyze('let x: boolean = "a" < 2;')

    assert "operador-relacional-tipo-invalido" in _rules(analyzer)


def test_equality_between_incompatible_types_is_reported():
    analyzer = _analyze('let x: boolean = true == "text";')

    assert "comparacion-tipos-incompatibles" in _rules(analyzer)


def test_equality_between_numeric_types_is_valid():
    analyzer = _analyze("let x: boolean = 1 == 2;")

    assert not analyzer.errors.has_errors()


def test_unary_minus_requires_numeric_operand():
    analyzer = _analyze("let x: integer = -true;")

    assert "operador-unario-tipo-invalido" in _rules(analyzer)


def test_unary_not_requires_boolean_operand():
    analyzer = _analyze("let x: boolean = !1;")

    assert "operador-unario-tipo-invalido" in _rules(analyzer)


def test_array_literal_with_mixed_incompatible_types_is_reported():
    analyzer = _analyze('let x: integer[] = [1, "two", 3];')

    assert "arreglo-tipos-inconsistentes" in _rules(analyzer)


def test_array_literal_with_homogeneous_types_is_valid():
    analyzer = _analyze("let x: integer[] = [1, 2, 3];")

    assert not analyzer.errors.has_errors()


def test_array_index_must_be_integer():
    analyzer = _analyze('let arr: integer[] = [1, 2, 3]; let y: integer = arr["a"];')

    assert "indice-no-entero" in _rules(analyzer)


def test_indexing_a_non_array_is_reported():
    analyzer = _analyze("let x: integer = 5; let y: integer = x[0];")

    assert "indice-sobre-no-arreglo" in _rules(analyzer)


def test_ternary_condition_must_be_boolean():
    analyzer = _analyze("let x: integer = 1 ? 2 : 3;")

    assert "condicion-no-booleana" in _rules(analyzer)


def test_ternary_with_boolean_condition_is_valid():
    analyzer = _analyze("let x: integer = true ? 2 : 3;")

    assert not analyzer.errors.has_errors()
