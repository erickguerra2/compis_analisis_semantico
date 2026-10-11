import pytest

from helpers import compile_source


def test_arguments_and_result_exact_tac():
    result = compile_source("function add(a: integer, b: integer): integer { return a + b; } let x = add(1 + 2, 3 * 4);")
    assert not result.errors
    assert result.tac == ["begin_func main", "t0 = 1 + 2", "t1 = 3 * 4", "param t0", "param t1", "t0 = call add, 2", "x = t0", "end_func main", "begin_func add", "t0 = a + b", "return t0", "end_func add"]
    assert result.emitter.function_temps == {"main": 2, "add": 1}
    assert result.emitter.live_temps() == 0


def test_void_call_and_implicit_return():
    result = compile_source("function f() { print(1); } f();")
    assert result.tac == ["begin_func main", "call f, 0", "end_func main", "begin_func f", "print 1", "return", "end_func f"]


def test_nested_functions_queue_and_capture():
    result = compile_source("function outer(x: integer): integer { function inner(y: integer): integer { return x + y; } return inner(2); } function other() { return; } print(outer(1));")
    assert not result.errors
    assert result.tac == ["begin_func main", "param 1", "t0 = call outer, 1", "print t0", "end_func main", "begin_func outer", "param 2", "t0 = call outer.inner, 1", "return t0", "end_func outer", "begin_func other", "return", "end_func other", "begin_func outer.inner", "t0 = x + y", "return t0", "end_func outer.inner"]
    record = result.analyzer.activation_records["outer.inner"]
    assert record.access_parent == "outer"
    assert record.depth == 2


def test_recursion():
    result = compile_source("function f(n: integer): integer { if (n == 0) { return 1; } return n * f(n - 1); } print(f(3));")
    assert not result.errors
    assert result.tac.count("t0 = call f, 1") == 2
    assert "t0 = n * t0" in result.tac


def test_return_unwinds_all_handlers_and_releases_result():
    result = compile_source("function f(): integer { try { try { return 1 + 2; } catch (e) { print(e); } } catch (e) { print(e); } return 0; }")
    assert not result.errors
    index = result.tac.index("return t0")
    assert result.tac[index-3:index+1] == ["t0 = 1 + 2", "try_end", "try_end", "return t0"]
    assert result.emitter.live_temps() == 0


@pytest.mark.parametrize("source", [
    "function f(x: integer) {} f();",
    "function f(x: integer) {} f(true);",
    "return 1;",
    "function f(): integer { return true; }",
])
def test_invalid_program_has_no_tac(source):
    result = compile_source(source)
    assert result.errors
    assert result.tac == []


def test_names_follow_declaration_order_in_pending_bodies():
    result = compile_source("function f(x: integer) { print(x); } let x = 1; f(x);")
    assert "x_1 = 1" in result.tac
    assert "param x_1" in result.tac
    assert "print x" in result.tac
