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


@pytest.mark.parametrize(
    "source, rule",
    [
        ("break;", "break-fuera-de-bucle"),
        ("continue;", "continue-fuera-de-bucle"),
        ("if (true) { break; }", "break-fuera-de-bucle"),
        ("if (1) { print(1); }", "condicion-no-booleana"),
        ("let i = 0; while (i) { i = i + 1; }", "condicion-no-booleana"),
    ],
)
def test_invalid_control_flow_generates_no_tac(source, rule):
    assert rule in rules(source)
