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


def test_if_condition_must_be_boolean():
    analyzer = _analyze("if (1) { print(1); }")

    assert "condicion-no-booleana" in _rules(analyzer)


def test_if_condition_with_boolean_is_valid():
    analyzer = _analyze("if (true) { print(1); }")

    assert not analyzer.errors.has_errors()


def test_while_condition_must_be_boolean():
    analyzer = _analyze('while ("a") { print(1); }')

    assert "condicion-no-booleana" in _rules(analyzer)


def test_do_while_condition_must_be_boolean():
    analyzer = _analyze("do { print(1); } while (1);")

    assert "condicion-no-booleana" in _rules(analyzer)


def test_for_condition_must_be_boolean():
    analyzer = _analyze("for (let i: integer = 0; i; i = i + 1) { print(i); }")

    assert "condicion-no-booleana" in _rules(analyzer)


def test_for_condition_with_boolean_is_valid():
    analyzer = _analyze("for (let i: integer = 0; i < 10; i = i + 1) { print(i); }")

    assert not analyzer.errors.has_errors()


def test_break_outside_loop_is_reported():
    analyzer = _analyze("break;")

    assert "break-fuera-de-bucle" in _rules(analyzer)


def test_continue_outside_loop_is_reported():
    analyzer = _analyze("continue;")

    assert "continue-fuera-de-bucle" in _rules(analyzer)


def test_break_inside_while_is_valid():
    analyzer = _analyze("while (true) { break; }")

    assert not analyzer.errors.has_errors()


def test_break_inside_foreach_is_valid():
    analyzer = _analyze("let items: integer[] = [1, 2, 3]; foreach (item in items) { break; }")

    assert not analyzer.errors.has_errors()


def test_return_outside_function_is_reported():
    analyzer = _analyze("return 1;")

    assert "return-fuera-de-funcion" in _rules(analyzer)


def test_return_type_mismatch_is_reported():
    source = """
    function fact(n: integer): integer {
        return true;
    }
    """

    analyzer = _analyze(source)

    assert "return-tipo-incompatible" in _rules(analyzer)


def test_return_type_match_is_valid():
    source = """
    function fact(n: integer): integer {
        return n;
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()


def test_switch_case_with_incompatible_type_is_reported():
    source = """
    let x: integer = 1;
    switch (x) {
        case true:
            print(1);
    }
    """

    analyzer = _analyze(source)

    assert "switch-case-tipo-incompatible" in _rules(analyzer)


def test_switch_case_with_compatible_type_is_valid():
    source = """
    let x: integer = 1;
    switch (x) {
        case 1:
            print(1);
        default:
            print(0);
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()
