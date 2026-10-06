from tests.helpers import compile_source


def test_arithmetic_recycles_temporaries():
    result = compile_source("let a = 1; let b = 2; let c = 3; let d = 4; let x = a * b + c * d;")
    assert result.errors == []
    assert result.tac == [
        "begin_func main", "a = 1", "b = 2", "c = 3", "d = 4",
        "t0 = a * b", "t1 = c * d", "t0 = t0 + t1", "x = t0", "end_func main",
    ]
    assert result.emitter.live_temps() == 0
    assert result.emitter.function_temps["main"] == 2


def test_short_circuit_and_ternary_keep_result_alive():
    result = compile_source(
        "let a: boolean = true; let b: boolean = false; "
        "let both = a && b; let value = both ? 1 : 2;"
    )
    assert result.errors == []
    assert result.tac == [
        "begin_func main", "a = true", "b = false", "t0 = a", "ifFalse t0 goto L0",
        "t0 = b", "L0:", "both = t0", "ifFalse both goto L1", "t0 = 1", "goto L2",
        "L1:", "t0 = 2", "L2:", "value = t0", "end_func main",
    ]
    assert result.emitter.live_temps() == 0


def test_strings_are_interned_and_values_are_converted():
    result = compile_source('let n = 5; let text = "n=" + n; print(text); print("n=");')
    assert result.errors == []
    assert result.tac == [
        "begin_func main", "n = 5", "t0 = to_str n", "t0 = concat .str0, t0",
        "text = t0", "print text", "print .str0", "end_func main",
    ]
    assert result.emitter.strings == {".str0": "n="}


def test_unary_relational_assignment_expression_and_shadow_names():
    result = compile_source("let x = 1; { let x = -2; x = x + 1; print(x); } print(x < 3);")
    assert result.errors == []
    assert "x_1 = t0" in result.tac
    assert "print x_1" in result.tac
    assert result.emitter.live_temps() == 0


def test_semantic_error_produces_no_tac():
    result = compile_source("let x: integer = true;")
    assert result.errors
    assert result.tac == []
    assert result.emitter is None
