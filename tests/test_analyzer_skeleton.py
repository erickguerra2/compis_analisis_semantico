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


def test_variable_declaration_is_registered_in_global_scope():
    analyzer = _analyze("let x: integer = 1;")

    symbol = analyzer.symbol_table.global_scope.resolve_local("x")

    assert symbol is not None
    assert symbol.type.name == "integer"


def test_undeclared_variable_is_reported():
    analyzer = _analyze("print(y);")

    assert analyzer.errors.has_errors()
    assert analyzer.errors.errors[0].rule == "uso-variable-no-declarada"


def test_redeclaration_in_same_scope_is_reported():
    analyzer = _analyze("let x: integer = 1; let x: integer = 2;")

    assert any(error.rule == "redeclaracion-mismo-ambito" for error in analyzer.errors.errors)


def test_block_gets_its_own_scope_so_shadowing_does_not_error():
    analyzer = _analyze("let x: integer = 1; { let x: integer = 2; }")

    assert not analyzer.errors.has_errors()


def test_function_declares_parameters_and_can_recurse():
    source = """
    function fact(n: integer): integer {
        return fact(n);
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()
    function_symbol = analyzer.symbol_table.global_scope.resolve_local("fact")
    assert function_symbol is not None
    assert function_symbol.params[0].name == "integer"
    assert function_symbol.return_type.name == "integer"


def test_nested_function_resolves_enclosing_variable():
    source = """
    function outer(): integer {
        let counter: integer = 0;
        function inner(): integer {
            return counter;
        }
        return counter;
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()


def test_class_declaration_registers_members_in_its_own_scope():
    source = """
    class Animal {
        function speak(): string {
            return "...";
        }
    }
    """

    analyzer = _analyze(source)

    assert not analyzer.errors.has_errors()
    class_symbol = analyzer.symbol_table.global_scope.resolve_local("Animal")
    assert class_symbol is not None
    assert class_symbol.class_scope.resolve_local("speak") is not None
