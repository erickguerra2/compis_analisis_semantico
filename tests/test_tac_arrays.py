import pytest

from tests.helpers import compile_source


def tac(source):
    result = compile_source(source)
    assert result.errors == []
    assert result.emitter.live_temps() == 0
    return result.tac[1:result.tac.index("end_func main")]


def rules(source):
    result = compile_source(source)
    assert result.tac == []
    return [error.rule for error in result.errors]


def test_array_literal_reserves_and_stores_each_element():
    assert tac("let a = [1, 2 * 3, 3];") == [
        "t0 = new_array 3", "t0[0] = 1", "t1 = 2 * 3", "t0[1] = t1", "t0[2] = 3", "a = t0",
    ]


def test_empty_and_nested_array_literals():
    assert tac("let e: integer[] = []; let m: integer[][] = [[1, 2], [3]];") == [
        "t0 = new_array 0", "e = t0",
        "t0 = new_array 2",
        "t1 = new_array 2", "t1[0] = 1", "t1[1] = 2", "t0[0] = t1",
        "t1 = new_array 1", "t1[0] = 3", "t0[1] = t1",
        "m = t0",
    ]


def test_index_read_checks_bounds_first():
    assert tac("let a = [5]; let i = 0; print(a[i + 1]);")[4:] == [
        "t0 = i + 1", "bounds a, t0", "t0 = a[t0]", "print t0",
    ]


def test_index_write_checks_bounds_and_value_is_the_assigned_operand():
    assert tac("let a = [5, 6]; a[1] = 7; let x = a[0] = 2 + 3;")[4:] == [
        "bounds a, 1", "a[1] = 7",
        "t0 = 2 + 3", "bounds a, 0", "a[0] = t0", "x = t0",
    ]


def test_multidimensional_read_and_write():
    lines = tac("let m = [[1, 2], [3, 4]]; let i = 1; let j = 0; print(m[i][j]); m[i][j] = 9;")
    assert lines[lines.index("j = 0") + 1:] == [
        "bounds m, i", "t0 = m[i]", "bounds t0, j", "t0 = t0[j]", "print t0",
        "bounds m, i", "t0 = m[i]", "bounds t0, j", "t0[j] = 9",
    ]


def test_index_on_call_result_and_temps_are_recycled():
    source = "function f(): integer[] { return [1, 2]; } let a = [3, 4]; print(f()[0] + a[1] * a[0]);"
    assert tac(source)[4:] == [
        "t0 = call f, 0", "bounds t0, 0", "t0 = t0[0]",
        "bounds a, 1", "t1 = a[1]", "bounds a, 0", "t2 = a[0]", "t1 = t1 * t2",
        "t0 = t0 + t1", "print t0",
    ]


def test_array_fields_and_elements_of_objects():
    source = "class Bag { let items: integer[] = [1]; } let b: Bag = new Bag(); b.items[0] = b.items[0] + 1;"
    assert tac(source) == [
        "t0 = new Bag", "t1 = new_array 1", "t1[0] = 1", "t0.items = t1", "b = t0",
        "t0 = b.items", "bounds t0, 0", "t0 = t0[0]", "t0 = t0 + 1",
        "t1 = b.items", "bounds t1, 0", "t1[0] = t0",
    ]


def test_foreach_exact_pattern_with_break_and_continue():
    source = "let numbers = [1, 2, 3]; foreach (n in numbers) { if (n == 2) { continue; } if (n > 2) { break; } print(n); }"
    assert tac(source)[5:] == [
        "t0 = numbers", "t1 = len t0", "t2 = 0",
        "L0:", "t3 = t2 < t1", "ifFalse t3 goto L2",
        "n = t0[t2]",
        "t3 = n == 2", "ifFalse t3 goto L3", "goto L1", "L3:",
        "t3 = n > 2", "ifFalse t3 goto L4", "goto L2", "L4:",
        "print n",
        "L1:", "t2 = t2 + 1", "goto L0", "L2:",
    ]


def test_foreach_over_temporary_does_not_copy_it():
    lines = tac("foreach (x in [7, 8]) { print(x); }")
    assert lines[:6] == ["t0 = new_array 2", "t0[0] = 7", "t0[1] = 8", "t1 = len t0", "t2 = 0", "L0:"]
    assert "x = t0[t2]" in lines


def test_nested_foreach_keeps_outer_temporaries_alive():
    result = compile_source("let m = [[1], [2]]; foreach (row in m) { foreach (v in row) { print(v); } }")
    assert result.errors == []
    lines = result.tac
    assert "row = t0[t2]" in lines
    assert "v = t3[t5]" in lines
    assert result.emitter.function_temps["main"] == 7
    assert result.emitter.live_temps() == 0


def test_foreach_inside_function_and_shadowed_iteration_variable():
    source = "let n = 0; function sum(xs: integer[]): integer { let s = 0; foreach (n in xs) { s = s + n; } return s; }"
    result = compile_source(source)
    assert result.errors == []
    body = result.tac[result.tac.index("begin_func sum"):]
    assert body[:4] == ["begin_func sum", "s = 0", "t0 = xs", "t1 = len t0"]
    assert "n_1 = t0[t2]" in body
    assert "t3 = s + n_1" in body


def test_out_of_range_message_is_interned_once():
    result = compile_source('let a = [1]; print(a[0]); print(a[0]); print("fin");')
    assert result.emitter.strings == {".str0": "indice fuera de rango", ".str1": "fin"}
    no_index = compile_source("let a = [1];")
    assert no_index.emitter.strings == {}


def test_runtime_error_inside_try_is_caught_by_the_handler():
    source = 'let lista = [1, 2, 3]; try { let peligro = lista[100]; } catch (err) { print("Error atrapado: " + err); }'
    result = compile_source(source)
    assert result.emitter.strings == {".str0": "indice fuera de rango", ".str1": "Error atrapado: "}
    assert tac(source)[5:] == [
        "try_begin L0",
        "bounds lista, 100", "t0 = lista[100]", "peligro = t0",
        "try_end", "goto L1",
        "L0:", "catch err", "t0 = concat .str1, err", "print t0",
        "L1:",
    ]


def test_break_out_of_try_inside_foreach_unregisters_handler():
    source = "let a = [1, 2]; foreach (x in a) { try { if (x == 2) { break; } print(a[x]); } catch (e) { print(e); } }"
    lines = tac(source)
    jump = lines.index("goto L2")
    assert lines[jump - 1] == "try_end"
    assert lines.count("try_end") == 2


@pytest.mark.parametrize("source, rule", [
    ('let a = [1, 2]; print(a["0"]);', "indice-no-entero"),
    ("let x = 5; print(x[0]);", "indice-sobre-no-arreglo"),
    ('let a = [1, "dos"];', "arreglo-tipos-inconsistentes"),
    ('let a: integer[] = [1]; a[0] = "x";', "asignacion-tipo-incompatible"),
    ("let m: integer[][] = [1, 2];", "asignacion-tipo-incompatible"),
    ("foreach (x in [1]) { print(y); }", "uso-variable-no-declarada"),
    ("foreach (x in [1]) { } print(x);", "uso-variable-no-declarada"),
])
def test_invalid_array_programs_generate_no_tac(source, rule):
    assert rule in rules(source)
