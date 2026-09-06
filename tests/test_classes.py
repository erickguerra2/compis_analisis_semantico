from antlr4 import CommonTokenStream, InputStream

from generated.CompiscriptLexer import CompiscriptLexer
from generated.CompiscriptParser import CompiscriptParser
from semantic.analyzer import SemanticAnalyzer


def _analyze(source: str) -> SemanticAnalyzer:
    lexer = CompiscriptLexer(InputStream(source))
    parser = CompiscriptParser(CommonTokenStream(lexer))
    tree = parser.program()
    analyzer = SemanticAnalyzer()
    analyzer.visit(tree)
    return analyzer


def _rules(analyzer: SemanticAnalyzer):
    return [error.rule for error in analyzer.errors.errors]


def test_own_and_inherited_members_are_resolved():
    analyzer = _analyze(
        """
        class Animal {
            function speak(): string { return "sound"; }
        }
        class Dog: Animal {
            let age: integer = 2;
        }
        let dog: Dog = new Dog();
        let sound: string = dog.speak();
        let age: integer = dog.age;
        """
    )

    assert not analyzer.errors.has_errors()


def test_method_can_access_member_declared_later_in_class():
    analyzer = _analyze(
        """
        class Counter {
            function get(): integer { return this.value; }
            let value: integer = 0;
        }
        """
    )

    assert not analyzer.errors.has_errors()


def test_subclass_is_assignable_to_base_but_not_the_other_way_around():
    analyzer = _analyze(
        """
        class Animal {}
        class Dog: Animal {}
        let animal: Animal = new Dog();
        let dog: Dog = new Animal();
        """
    )

    incompatible = [
        error for error in analyzer.errors.errors if error.rule == "asignacion-tipo-incompatible"
    ]
    assert len(incompatible) == 1


def test_missing_member_and_dot_on_primitive_are_reported():
    analyzer = _analyze(
        """
        class Box {}
        let box: Box = new Box();
        print(box.missing);
        let number: integer = 1;
        print(number.value);
        """
    )

    assert "miembro-no-existente" in _rules(analyzer)
    assert "acceso-miembro-sobre-no-objeto" in _rules(analyzer)


def test_constructor_validates_argument_count_and_types():
    valid = _analyze(
        """
        class Person {
            let name: string;
            function constructor(name: string) { this.name = name; }
        }
        let person: Person = new Person("Ada");
        """
    )
    wrong_count = _analyze(
        """
        class Person { function constructor(name: string) {} }
        let person: Person = new Person();
        """
    )
    wrong_type = _analyze(
        """
        class Person { function constructor(name: string) {} }
        let person: Person = new Person(42);
        """
    )

    assert not valid.errors.has_errors()
    assert "llamada-numero-argumentos-invalido" in _rules(wrong_count)
    assert "llamada-tipo-argumento-invalido" in _rules(wrong_type)


def test_new_unknown_class_and_arguments_without_constructor_are_reported():
    analyzer = _analyze(
        """
        class Empty {}
        let first = new Missing();
        let second: Empty = new Empty(1);
        """
    )

    assert "new-clase-no-declarada" in _rules(analyzer)
    assert "constructor-numero-argumentos-invalido" in _rules(analyzer)


def test_this_is_only_valid_inside_methods():
    valid = _analyze(
        """
        class Counter {
            let value: integer = 0;
            function get(): integer { return this.value; }
        }
        """
    )
    invalid = _analyze("print(this);")

    assert not valid.errors.has_errors()
    assert "this-fuera-de-metodo" in _rules(invalid)


def test_property_assignment_checks_type_and_constant_reassignment():
    analyzer = _analyze(
        """
        class Config {
            let retries: integer = 1;
            const name: string = "main";
            function update() {
                this.retries = "many";
                this.name = "other";
            }
        }
        """
    )

    assert "asignacion-tipo-incompatible" in _rules(analyzer)
    assert "asignacion-a-constante" in _rules(analyzer)


def test_unknown_base_class_and_self_inheritance_are_reported():
    analyzer = _analyze(
        """
        class Orphan: Missing {}
        class Loop: Loop {}
        """
    )

    assert "clase-base-no-declarada" in _rules(analyzer)
    assert "herencia-ciclica" in _rules(analyzer)
