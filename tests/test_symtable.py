from semantic.types import BOOLEAN, INTEGER
from symtable.scope import ScopeKind
from symtable.symbol import Symbol, SymbolCategory
from symtable.symbol_table import SymbolTable


def test_declare_and_resolve():
    table = SymbolTable()
    symbol = Symbol(name="x", category=SymbolCategory.VARIABLE, type=INTEGER)

    assert table.declare(symbol) is None
    assert table.resolve("x") is symbol


def test_resolve_missing_symbol_returns_none():
    table = SymbolTable()

    assert table.resolve("missing") is None


def test_duplicate_declaration_in_same_scope_is_reported():
    table = SymbolTable()
    table.declare(Symbol(name="x", category=SymbolCategory.VARIABLE, type=INTEGER))

    error = table.declare(Symbol(name="x", category=SymbolCategory.VARIABLE, type=BOOLEAN))

    assert error is not None


def test_nested_scope_resolves_outer_symbol():
    table = SymbolTable()
    table.declare(Symbol(name="x", category=SymbolCategory.VARIABLE, type=INTEGER))

    table.enter_scope(ScopeKind.BLOCK)
    resolved = table.resolve("x")
    table.exit_scope()

    assert resolved is not None
    assert resolved.type is INTEGER


def test_shadowing_in_nested_scope_hides_outer_without_erroring():
    table = SymbolTable()
    table.declare(Symbol(name="x", category=SymbolCategory.VARIABLE, type=INTEGER))

    table.enter_scope(ScopeKind.BLOCK)
    error = table.declare(Symbol(name="x", category=SymbolCategory.VARIABLE, type=BOOLEAN))
    inner = table.resolve("x")
    table.exit_scope()
    outer = table.resolve("x")

    assert error is None
    assert inner.type is BOOLEAN
    assert outer.type is INTEGER


def test_nested_function_scope_resolves_enclosing_symbol():
    table = SymbolTable()
    table.declare(Symbol(name="counter", category=SymbolCategory.VARIABLE, type=INTEGER))

    table.enter_scope(ScopeKind.FUNCTION)
    table.enter_scope(ScopeKind.FUNCTION)
    resolved = table.resolve("counter")
    table.exit_scope()
    table.exit_scope()

    assert resolved is not None


def test_resolve_member_walks_the_inheritance_chain():
    table = SymbolTable()
    animal = Symbol(name="Animal", category=SymbolCategory.CLASS)
    table.declare(animal)
    animal.class_scope = table.enter_scope(ScopeKind.CLASS)
    speak = Symbol(name="speak", category=SymbolCategory.FUNCTION)
    table.declare(speak)
    table.exit_scope()

    dog = Symbol(name="Dog", category=SymbolCategory.CLASS, parent_class="Animal")
    table.declare(dog)
    dog.class_scope = table.enter_scope(ScopeKind.CLASS)
    table.exit_scope()

    assert table.resolve_member("Dog", "speak") is speak


def test_missing_inherited_member_returns_none():
    table = SymbolTable()
    animal = Symbol(name="Animal", category=SymbolCategory.CLASS)
    table.declare(animal)
    animal.class_scope = table.enter_scope(ScopeKind.CLASS)
    table.exit_scope()

    dog = Symbol(name="Dog", category=SymbolCategory.CLASS, parent_class="Animal")
    table.declare(dog)
    dog.class_scope = table.enter_scope(ScopeKind.CLASS)
    table.exit_scope()

    assert table.resolve_member("Dog", "missing") is None


def test_memory_offsets_and_activation_records():
    from helpers import compile_source
    result = compile_source("let g = 1; { let h = true; } function f(p: integer) { let a = 1; { let b = 2; } { let c = 3; } print(a + p); function inner(q: integer) { print(a + q); } inner(2); }")
    assert not result.errors
    records = result.analyzer.activation_records
    f = records["f"]
    assert [(s.name, s.offset, s.storage, s.depth, s.size) for s in f.parameters + f.locals] == [("p", 12, "param", 1, 4), ("a", 16, "local", 1, 4), ("b", 20, "local", 1, 4), ("c", 24, "local", 1, 4)]
    assert f.temp_offset(0) == 28
    assert f.size == 32
    assert (f.return_address_offset, f.control_link_offset, f.access_link_offset) == (0, 4, 8)
    assert records["f.inner"].parameters[0].offset == 12
    assert records["f.inner"].depth == 2
    globals_ = [s for scope in result.analyzer.symbol_table.scopes for s in scope.symbols.values() if s.storage == "global"]
    assert [(s.name, s.offset, s.depth) for s in globals_] == [("g", 0, 0), ("h", 4, 0)]
    import pytest
    with pytest.raises(IndexError):
        f.temp_offset(1)


def test_type_sizes_are_four_bytes_for_values_and_references():
    from semantic.types import size_of, INTEGER, BOOLEAN, STRING, NULL, VOID, ArrayType, ClassType
    assert [size_of(t) for t in [INTEGER, BOOLEAN, STRING, NULL, ArrayType(INTEGER), ClassType("C")]] == [4] * 6
    assert size_of(VOID) == 0


def test_memory_follows_source_order_across_scopes():
    from helpers import compile_source
    result = compile_source("let a = 0; { let b = 1; } let c = 2; function f() { { let x = 1; } let y = 2; }")
    assert not result.errors
    symbols = {s.name: s for sc in result.analyzer.symbol_table.scopes for s in sc.symbols.values()}
    assert [symbols[n].offset for n in ["a", "b", "c"]] == [0, 4, 8]
    assert [symbols[n].offset for n in ["x", "y"]] == [12, 16]


def _class_program(source):
    from antlr4 import CommonTokenStream, InputStream
    from generated.CompiscriptLexer import CompiscriptLexer
    from generated.CompiscriptParser import CompiscriptParser
    from semantic.analyzer import SemanticAnalyzer
    from symtable.activation import MemoryLayout
    tree = CompiscriptParser(CommonTokenStream(CompiscriptLexer(InputStream(source)))).program()
    analyzer = SemanticAnalyzer()
    analyzer.visit(tree)
    assert not analyzer.errors.has_errors()
    MemoryLayout(analyzer, tree)
    return analyzer


def test_field_offsets_put_inherited_fields_first():
    analyzer = _class_program(
        "class A { let x: integer; let y: string; } "
        "class B : A { let z: boolean; } "
        "class C : B { let w: integer; }"
    )
    layouts = analyzer.class_layouts
    assert [(f.name, f.offset, f.storage, f.size) for f in layouts["C"]] == [
        ("x", 0, "field", 4), ("y", 4, "field", 4), ("z", 8, "field", 4), ("w", 12, "field", 4)]
    sizes = {s.name: s.size for s in analyzer.symbol_table.global_scope.symbols.values()}
    assert sizes == {"A": 8, "B": 12, "C": 16}


def test_methods_are_not_fields_and_redeclared_field_reuses_slot():
    analyzer = _class_program(
        "class A { let x: integer; function f() {} let y: integer; } "
        "class B : A { let y: integer; let z: integer; function g() {} }"
    )
    assert [(f.name, f.offset) for f in analyzer.class_layouts["A"]] == [("x", 0), ("y", 4)]
    assert [(f.name, f.offset) for f in analyzer.class_layouts["B"]] == [("x", 0), ("y", 4), ("z", 8)]
    assert analyzer.class_layouts["B"][1].scope is not analyzer.class_layouts["A"][1].scope
    empty = _class_program("class E { function f() {} }")
    assert empty.class_layouts["E"] == []
    assert empty.symbol_table.global_scope.symbols["E"].size == 0


def test_method_record_reserves_this_before_parameters():
    analyzer = _class_program(
        "class P { let n: integer; function set(v: integer) { let old = this.n; this.n = v; } }"
    )
    record = analyzer.activation_records["P.set"]
    assert [(s.name, s.offset, s.storage) for s in record.parameters + record.locals] == [
        ("this", 12, "param"), ("v", 16, "param"), ("old", 20, "local")]
