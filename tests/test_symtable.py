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
