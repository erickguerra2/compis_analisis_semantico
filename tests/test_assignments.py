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


def test_variable_declaration_with_matching_type_is_valid():
    analyzer = _analyze("let x: integer = 5;")

    assert not analyzer.errors.has_errors()


def test_variable_declaration_with_mismatched_type_is_reported():
    analyzer = _analyze("let x: integer = true;")

    assert "asignacion-tipo-incompatible" in _rules(analyzer)


def test_variable_declaration_infers_type_from_initializer_when_no_annotation():
    analyzer = _analyze("let x = 5; let y: integer = x;")

    assert not analyzer.errors.has_errors()


def test_integer_is_assignable_to_float_variable():
    analyzer = _analyze("let x: float = 5;")

    assert not analyzer.errors.has_errors()


def test_constant_declaration_with_mismatched_type_is_reported():
    analyzer = _analyze('const x: integer = "hola";')

    assert "asignacion-tipo-incompatible" in _rules(analyzer)


def test_reassigning_a_constant_is_reported():
    analyzer = _analyze("const x: integer = 1; x = 2;")

    assert "asignacion-a-constante" in _rules(analyzer)


def test_reassigning_a_variable_with_wrong_type_is_reported():
    analyzer = _analyze("let x: integer = 1; x = true;")

    assert "asignacion-tipo-incompatible" in _rules(analyzer)


def test_reassigning_a_variable_with_matching_type_is_valid():
    analyzer = _analyze("let x: integer = 1; x = 2;")

    assert not analyzer.errors.has_errors()


def test_assignment_to_undeclared_variable_is_reported():
    analyzer = _analyze("y = 2;")

    assert "uso-variable-no-declarada" in _rules(analyzer)


def test_nested_assignment_expression_checks_constant_reassignment():
    source = """
    const x: integer = 1;
    function useValue(n: integer): integer {
        return n;
    }
    let y: integer = useValue(x = 2);
    """

    analyzer = _analyze(source)

    assert "asignacion-a-constante" in _rules(analyzer)
