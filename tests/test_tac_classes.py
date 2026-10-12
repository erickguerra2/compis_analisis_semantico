import pytest

from tests.helpers import compile_source


ANIMALS = """
class Animal {
  let name: string;
  let legs: integer = 4;
  function constructor(name: string) { this.name = name; }
  function speak(): string { return this.name + " hace ruido"; }
}
class Dog : Animal {
  let tricks: integer = 1 + 2;
  function speak(): string { return this.name + " ladra"; }
  function rename(n: string) { this.name = n; }
}
"""


def tac(source):
    result = compile_source(source)
    assert result.errors == []
    assert result.emitter.live_temps() == 0
    return result.tac


def rules(source):
    result = compile_source(source)
    assert result.tac == []
    return [error.rule for error in result.errors]


def test_class_declaration_emits_nothing_in_main_and_queues_methods():
    assert tac(ANIMALS) == [
        "begin_func main", "end_func main",
        "begin_func Animal.constructor", "this.name = name", "return", "end_func Animal.constructor",
        "begin_func Animal.speak", "t0 = this.name", "t0 = concat t0, .str0", "return t0", "end_func Animal.speak",
        "begin_func Dog.speak", "t0 = this.name", "t0 = concat t0, .str1", "return t0", "end_func Dog.speak",
        "begin_func Dog.rename", "this.name = n", "return", "end_func Dog.rename",
    ]


def test_new_runs_field_initializers_from_root_and_inherited_constructor():
    assert tac(ANIMALS + 'let d: Dog = new Dog("Rex");')[1:10] == [
        "t0 = new Dog", "t0.legs = 4", "t1 = 1 + 2", "t0.tricks = t1",
        "param t0", "param .str0", "call Animal.constructor, 2", "d = t0", "end_func main",
    ]


def test_new_without_constructor_only_reserves_and_initializes():
    assert tac("class P { let x: integer = 1; let y: integer; } let p: P = new P();")[:5] == [
        "begin_func main", "t0 = new P", "t0.x = 1", "p = t0", "end_func main",
    ]


def test_constructor_of_nearest_ancestor_is_used():
    source = (
        "class A { function constructor(v: integer) {} } class B : A {} class C : B {} "
        "class D : C { function constructor() {} } let c: C = new C(5); let d: D = new D();"
    )
    lines = tac(source)
    assert lines[1:5] == ["t0 = new C", "param t0", "param 5", "call A.constructor, 2"]
    assert lines[6:9] == ["t0 = new D", "param t0", "call D.constructor, 1"]


def test_method_call_passes_receiver_and_dispatches_statically():
    lines = tac(ANIMALS + 'let d: Dog = new Dog("Rex"); let a: Animal = d; print(d.speak()); print(a.speak()); d.rename("Toby");')
    main = lines[lines.index("a = d"):lines.index("end_func main")]
    assert main == [
        "a = d",
        "param d", "t0 = call Dog.speak, 1", "print t0",
        "param a", "t0 = call Animal.speak, 1", "print t0",
        "param d", "param .str1", "call Dog.rename, 2",
    ]


def test_inherited_method_uses_the_class_that_declares_it():
    lines = tac("class A { function f(): integer { return 1; } } class B : A {} let b: B = new B(); print(b.f());")
    assert "t0 = call A.f, 1" in lines
    assert "B.f" not in " ".join(lines)


def test_this_inside_methods_reads_writes_and_calls():
    source = (
        "class Counter { let count: integer; "
        "function inc(step: integer) { this.count = this.count + step; } "
        "function twice(): integer { this.inc(1); return this.count * 2; } }"
    )
    lines = tac(source)
    assert lines[lines.index("begin_func Counter.inc"):] == [
        "begin_func Counter.inc", "t0 = this.count", "t0 = t0 + step", "this.count = t0", "return", "end_func Counter.inc",
        "begin_func Counter.twice", "param this", "param 1", "call Counter.inc, 2",
        "t0 = this.count", "t0 = t0 * 2", "return t0", "end_func Counter.twice",
    ]


def test_property_chains_reuse_the_same_temporary():
    source = (
        "class Node { let value: integer; let next: Node; } "
        "let n: Node = new Node(); n.next = new Node(); "
        "let v = n.next.value; n.next.value = 7; let x = n.next.next = null;"
    )
    assert tac(source)[1:] == [
        "t0 = new Node", "n = t0", "t0 = new Node", "n.next = t0",
        "t0 = n.next", "t0 = t0.value", "v = t0",
        "t0 = n.next", "t0.value = 7",
        "t0 = n.next", "t0.next = null", "x = null",
        "end_func main",
    ]


def test_method_on_temporaries_and_arguments_recycle_temps():
    source = (
        "class Calc { function add(a: integer, b: integer): integer { return a + b; } } "
        "let c: Calc = new Calc(); print(new Calc().add(1 * 2, 3) + c.add(4, 5));"
    )
    result = compile_source(source)
    main = result.tac[result.tac.index("c = t0") + 1:result.tac.index("end_func main")]
    assert main == [
        "t0 = new Calc", "t1 = 1 * 2", "param t0", "param t1", "param 3", "t0 = call Calc.add, 3",
        "param c", "param 4", "param 5", "t1 = call Calc.add, 3", "t0 = t0 + t1", "print t0",
    ]
    assert result.emitter.function_temps["main"] == 2
    assert result.emitter.live_temps() == 0


def test_nested_function_inside_method_is_queued_after_methods():
    lines = tac("class K { function f(): integer { function g(): integer { return 1; } return g(); } function h() {} }")
    units = [line for line in lines if line.startswith("begin_func")]
    assert units == ["begin_func main", "begin_func K.f", "begin_func K.h", "begin_func K.f.g"]
    assert "t0 = call K.f.g, 0" in lines


@pytest.mark.parametrize("source, rule", [
    ("class A {} let a: A = new A(); print(a.missing);", "miembro-no-existente"),
    ("class A { function f(x: integer) {} } let a: A = new A(); a.f();", "llamada-numero-argumentos-invalido"),
    ('class A { function f(x: integer) {} } let a: A = new A(); a.f("no");', "llamada-tipo-argumento-invalido"),
    ("let a = new Missing();", "new-clase-no-declarada"),
    ("class A {} let a: A = new A(1);", "constructor-numero-argumentos-invalido"),
    ("print(this);", "this-fuera-de-metodo"),
    ("let x = 5; print(x.campo);", "acceso-miembro-sobre-no-objeto"),
    ('class A { let n: integer; } let a: A = new A(); a.n = "texto";', "asignacion-tipo-incompatible"),
    ("class A {} class B : A {} let b: B = new A();", "asignacion-tipo-incompatible"),
])
def test_invalid_class_programs_generate_no_tac(source, rule):
    assert rule in rules(source)
