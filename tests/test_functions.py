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


def test_call_with_matching_arguments_is_valid():
    source = """
    function add(a: integer, b: integer): integer {
        return a + b;
    }
    let result: integer = add(1, 2);
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()


def test_call_with_too_few_arguments_is_reported():
    source = """
    function add(a: integer, b: integer): integer {
        return a + b;
    }
    add(1);
    """

    analyzer = _analyze(source)

    assert "llamada-numero-argumentos-invalido" in _rules(analyzer)


def test_call_with_too_many_arguments_is_reported():
    source = """
    function add(a: integer, b: integer): integer {
        return a + b;
    }
    add(1, 2, 3);
    """

    analyzer = _analyze(source)

    assert "llamada-numero-argumentos-invalido" in _rules(analyzer)


def test_call_with_incompatible_argument_type_is_reported():
    source = """
    function add(a: integer, b: integer): integer {
        return a + b;
    }
    add(1, true);
    """

    analyzer = _analyze(source)

    assert "llamada-tipo-argumento-invalido" in _rules(analyzer)


def test_call_on_non_function_value_is_reported():
    source = """
    let x: integer = 1;
    x(1);
    """

    analyzer = _analyze(source)

    assert "llamada-sobre-no-funcion" in _rules(analyzer)


def test_function_with_return_in_every_path_is_valid():
    source = """
    function sign(n: integer): integer {
        if (n < 0) {
            return -1;
        } else {
            return 1;
        }
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()


def test_function_missing_return_in_if_without_else_is_reported():
    source = """
    function sign(n: integer): integer {
        if (n < 0) {
            return 0 - 1;
        }
    }
    """

    analyzer = _analyze(source)

    assert "return-faltante-en-algun-camino" in _rules(analyzer)


def test_function_missing_return_when_only_inside_while_is_reported():
    source = """
    function first(n: integer): integer {
        while (n > 0) {
            return n;
        }
    }
    """

    analyzer = _analyze(source)

    assert "return-faltante-en-algun-camino" in _rules(analyzer)


def test_function_with_return_guaranteed_by_do_while_is_valid():
    source = """
    function first(n: integer): integer {
        do {
            return n;
        } while (n > 0);
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()


def test_function_without_declared_return_type_is_not_checked():
    source = """
    function noop() {
        let x: integer = 1;
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()
