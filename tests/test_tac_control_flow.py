import pytest

from tests.helpers import compile_source


def tac(source):
    result = compile_source(source)
    assert result.errors == []
    assert result.emitter.live_temps() == 0
    return result.tac[1:-1]


def rules(source):
    result = compile_source(source)
    assert result.tac == []
    return [error.rule for error in result.errors]


def test_if_without_else():
    assert tac("let a = 1; if (a < 2) { print(a); }") == [
        "a = 1", "t0 = a < 2", "ifFalse t0 goto L0", "print a", "L0:",
    ]


def test_if_with_else():
    assert tac("let a = 1; if (a < 2) { print(1); } else { print(2); }") == [
        "a = 1", "t0 = a < 2", "ifFalse t0 goto L0", "print 1", "goto L1", "L0:", "print 2", "L1:",
    ]


def test_if_uses_boolean_variable_directly():
    assert tac("let ok = true; if (ok) { print(1); }") == ["ok = true", "ifFalse ok goto L0", "print 1", "L0:"]


def test_while():
    assert tac("let i = 0; while (i < 3) { i = i + 1; }") == [
        "i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L1", "t0 = i + 1", "i = t0", "goto L0", "L1:",
    ]


def test_do_while():
    assert tac("let i = 0; do { i = i + 1; } while (i < 3);") == [
        "i = 0", "L0:", "t0 = i + 1", "i = t0", "L1:", "t0 = i < 3", "if t0 goto L0", "L2:",
    ]


def test_for():
    assert tac("for (let i = 0; i < 3; i = i + 1) { print(i); }") == [
        "i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L2", "print i",
        "L1:", "t0 = i + 1", "i = t0", "goto L0", "L2:",
    ]


def test_for_without_condition_or_update():
    assert tac("for (;;) { break; }") == ["L0:", "goto L2", "L1:", "goto L0", "L2:"]


def test_for_with_assignment_as_init_and_no_update():
    assert tac("let i = 0; for (i = 1; i < 3;) { i = i + 1; }") == [
        "i = 0", "i = 1", "L0:", "t0 = i < 3", "ifFalse t0 goto L2",
        "t0 = i + 1", "i = t0", "L1:", "goto L0", "L2:",
    ]


def test_break_and_continue_in_while():
    source = (
        "let i = 0; while (i < 9) { i = i + 1; "
        "if (i == 2) { continue; } if (i == 5) { break; } print(i); }"
    )
    assert tac(source) == [
        "i = 0", "L0:", "t0 = i < 9", "ifFalse t0 goto L1", "t0 = i + 1", "i = t0",
        "t0 = i == 2", "ifFalse t0 goto L2", "goto L0", "L2:",
        "t0 = i == 5", "ifFalse t0 goto L3", "goto L1", "L3:",
        "print i", "goto L0", "L1:",
    ]


def test_continue_in_do_while_jumps_to_condition():
    assert tac("let i = 0; do { i = i + 1; if (i == 2) { continue; } } while (i < 3);") == [
        "i = 0", "L0:", "t0 = i + 1", "i = t0", "t0 = i == 2", "ifFalse t0 goto L3", "goto L1", "L3:",
        "L1:", "t0 = i < 3", "if t0 goto L0", "L2:",
    ]


def test_continue_in_for_jumps_to_update():
    assert tac("for (let i = 0; i < 3; i = i + 1) { if (i == 1) { continue; } print(i); }") == [
        "i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L2",
        "t0 = i == 1", "ifFalse t0 goto L3", "goto L1", "L3:", "print i",
        "L1:", "t0 = i + 1", "i = t0", "goto L0", "L2:",
    ]


def test_nested_loops_break_targets_inner_loop():
    source = (
        "let i = 0; while (i < 2) { let j = 0; "
        "while (j < 2) { if (j == 1) { break; } j = j + 1; } i = i + 1; }"
    )
    assert tac(source) == [
        "i = 0", "L0:", "t0 = i < 2", "ifFalse t0 goto L1", "j = 0",
        "L2:", "t0 = j < 2", "ifFalse t0 goto L3",
        "t0 = j == 1", "ifFalse t0 goto L4", "goto L3", "L4:",
        "t0 = j + 1", "j = t0", "goto L2", "L3:",
        "t0 = i + 1", "i = t0", "goto L0", "L1:",
    ]


def test_condition_with_short_circuit_operators():
    assert tac("let a = 1; let b = 2; if (a < b && b < 3 || a == 0) { print(a); }") == [
        "a = 1", "b = 2",
        "t2 = a < b", "t1 = t2", "ifFalse t1 goto L2", "t2 = b < 3", "t1 = t2", "L2:",
        "t0 = t1", "if t0 goto L1", "t1 = a == 0", "t0 = t1", "L1:",
        "ifFalse t0 goto L0", "print a", "L0:",
    ]


def test_switch_falls_through_to_following_cases():
    assert tac("let x = 2; switch (x) { case 1: print(1); case 2: print(2); default: print(0); }") == [
        "x = 2", "t0 = x == 1", "if t0 goto L0", "t0 = x == 2", "if t0 goto L1", "goto L2",
        "L0:", "print 1", "L1:", "print 2", "L2:", "print 0", "L3:",
    ]


def test_switch_without_default_jumps_to_end():
    assert tac("let x = 2; switch (x) { case 1: print(1); break; case 2: print(2); break; }") == [
        "x = 2", "t0 = x == 1", "if t0 goto L0", "t0 = x == 2", "if t0 goto L1", "goto L2",
        "L0:", "print 1", "goto L2", "L1:", "print 2", "goto L2", "L2:",
    ]


def test_switch_keeps_subject_temporary_alive_while_comparing():
    assert tac("let x = 2; switch (x + 1) { case 1 + 1: print(1); break; default: print(0); }") == [
        "x = 2", "t0 = x + 1", "t1 = 1 + 1", "t1 = t0 == t1", "if t1 goto L0", "goto L1",
        "L0:", "print 1", "goto L2", "L1:", "print 0", "L2:",
    ]


def test_switch_with_only_default():
    assert tac("let x = 2; switch (x) { default: print(0); }") == ["x = 2", "goto L0", "L0:", "print 0", "L1:"]


def test_break_in_switch_inside_loop_leaves_only_the_switch():
    assert tac("let i = 0; while (i < 3) { switch (i) { case 1: break; default: print(i); } i = i + 1; }") == [
        "i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L1",
        "t0 = i == 1", "if t0 goto L2", "goto L3",
        "L2:", "goto L4", "L3:", "print i", "L4:",
        "t0 = i + 1", "i = t0", "goto L0", "L1:",
    ]


def test_continue_in_switch_inside_loop_targets_the_loop():
    source = "let i = 0; while (i < 3) { i = i + 1; switch (i) { case 1: continue; case 2: break; } print(i); }"
    assert tac(source) == [
        "i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L1", "t0 = i + 1", "i = t0",
        "t0 = i == 1", "if t0 goto L2", "t0 = i == 2", "if t0 goto L3", "goto L4",
        "L2:", "goto L0", "L3:", "goto L4", "L4:",
        "print i", "goto L0", "L1:",
    ]


def test_nested_switch_break_targets_inner_switch():
    assert tac("let x = 1; switch (x) { case 1: switch (x) { case 1: break; } print(9); break; }") == [
        "x = 1", "t0 = x == 1", "if t0 goto L0", "goto L1",
        "L0:", "t0 = x == 1", "if t0 goto L2", "goto L3", "L2:", "goto L3", "L3:",
        "print 9", "goto L1", "L1:",
    ]


def test_try_catch():
    assert tac("try { print(1); } catch (err) { print(err); }") == [
        "try_begin L0", "print 1", "try_end", "goto L1", "L0:", "catch err", "print err", "L1:",
    ]


def test_catch_variable_is_a_string():
    result = compile_source('try { print(1); } catch (err) { print("fallo: " + err); }')
    assert result.errors == []
    assert result.tac[1:-1] == [
        "try_begin L0", "print 1", "try_end", "goto L1",
        "L0:", "catch err", "t0 = concat .str0, err", "print t0", "L1:",
    ]
    assert result.emitter.strings == {".str0": "fallo: "}


def test_catch_variable_shadows_outer_name():
    assert tac("let err = 5; try { print(err); } catch (err) { print(err); } print(err);") == [
        "err = 5", "try_begin L0", "print err", "try_end", "goto L1",
        "L0:", "catch err_1", "print err_1", "L1:", "print err",
    ]


def test_break_inside_try_inside_loop_closes_the_try():
    source = "let i = 0; while (i < 3) { try { i = i + 1; if (i == 2) { break; } } catch (e) { print(e); } }"
    assert tac(source) == [
        "i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L1",
        "try_begin L2", "t0 = i + 1", "i = t0",
        "t0 = i == 2", "ifFalse t0 goto L4", "try_end", "goto L1", "L4:",
        "try_end", "goto L3", "L2:", "catch e", "print e", "L3:",
        "goto L0", "L1:",
    ]


def test_continue_and_break_close_every_open_try():
    source = (
        "let i = 0; while (i < 3) { i = i + 1; "
        "try { try { continue; } catch (a) { break; } } catch (b) { print(b); } }"
    )
    assert tac(source) == [
        "i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L1", "t0 = i + 1", "i = t0",
        "try_begin L2", "try_begin L4", "try_end", "try_end", "goto L0",
        "try_end", "goto L5", "L4:", "catch a", "try_end", "goto L1", "L5:",
        "try_end", "goto L3", "L2:", "catch b", "print b", "L3:",
        "goto L0", "L1:",
    ]


def test_break_in_loop_inside_try_does_not_close_the_try():
    assert tac("try { let i = 0; while (i < 2) { i = i + 1; break; } } catch (e) { print(e); }") == [
        "try_begin L0", "i = 0", "L2:", "t0 = i < 2", "ifFalse t0 goto L3",
        "t0 = i + 1", "i = t0", "goto L3", "goto L2", "L3:",
        "try_end", "goto L1", "L0:", "catch e", "print e", "L1:",
    ]


def test_switch_inside_try_inside_loop():
    source = (
        "let i = 0; while (i < 3) { try { switch (i) { case 0: break; case 1: continue; } "
        "i = i + 1; } catch (e) { print(e); } }"
    )
    assert tac(source) == [
        "i = 0", "L0:", "t0 = i < 3", "ifFalse t0 goto L1", "try_begin L2",
        "t0 = i == 0", "if t0 goto L4", "t0 = i == 1", "if t0 goto L5", "goto L6",
        "L4:", "goto L6", "L5:", "try_end", "goto L0", "L6:",
        "t0 = i + 1", "i = t0", "try_end", "goto L3", "L2:", "catch e", "print e", "L3:",
        "goto L0", "L1:",
    ]


@pytest.mark.parametrize(
    "source, rule",
    [
        ("break;", "break-fuera-de-bucle"),
        ("continue;", "continue-fuera-de-bucle"),
        ("if (true) { break; }", "break-fuera-de-bucle"),
        ("if (1) { print(1); }", "condicion-no-booleana"),
        ("let i = 0; while (i) { i = i + 1; }", "condicion-no-booleana"),
        ("let x = 2; switch (x) { case 1: continue; }", "continue-fuera-de-bucle"),
        ('let x = 2; switch (x) { case "a": print(1); }', "switch-case-tipo-incompatible"),
        ("try { print(1); } catch (e) { let n: integer = e; }", "asignacion-tipo-incompatible"),
        ("try { print(1); } catch (e) { let e = 2; }", "redeclaracion-mismo-ambito"),
        ("try { print(1); } catch (e) { print(1); } print(e);", "uso-variable-no-declarada"),
        ("try { let a = 1; } catch (e) { print(a); }", "uso-variable-no-declarada"),
    ],
)
def test_invalid_control_flow_generates_no_tac(source, rule):
    assert rule in rules(source)
