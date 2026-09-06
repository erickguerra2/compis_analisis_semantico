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


def test_code_after_return_in_block_is_reported():
    source = """
    function f(): integer {
        return 1;
        let x: integer = 2;
        print(x);
    }
    """

    analyzer = _analyze(source)

    assert "codigo-muerto" in _rules(analyzer)


def test_code_after_return_is_reported_only_once_per_block():
    source = """
    function f(): integer {
        return 1;
        let x: integer = 2;
        let y: integer = 3;
    }
    """

    analyzer = _analyze(source)

    assert _rules(analyzer).count("codigo-muerto") == 1


def test_code_after_break_in_loop_is_reported():
    source = """
    while (true) {
        break;
        print(1);
    }
    """

    analyzer = _analyze(source)

    assert "codigo-muerto" in _rules(analyzer)


def test_code_after_continue_in_loop_is_reported():
    source = """
    while (true) {
        continue;
        print(1);
    }
    """

    analyzer = _analyze(source)

    assert "codigo-muerto" in _rules(analyzer)


def test_return_as_last_statement_is_not_dead_code():
    source = """
    function f(): integer {
        let x: integer = 1;
        return x;
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()


def test_return_inside_if_does_not_mark_code_after_if_as_dead():
    source = """
    function f(n: integer): integer {
        if (n < 0) {
            return 0;
        }
        return n;
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()


def test_duplicate_parameter_names_are_reported():
    source = """
    function f(a: integer, a: integer): integer {
        return a;
    }
    """

    analyzer = _analyze(source)

    assert "redeclaracion-mismo-ambito" in _rules(analyzer)


def test_distinct_parameter_names_are_valid():
    source = """
    function f(a: integer, b: integer): integer {
        return a + b;
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()
