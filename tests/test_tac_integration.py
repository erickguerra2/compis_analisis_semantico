import re
from pathlib import Path

import pytest

from ide.app import create_app
from tests.helpers import compile_source

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "program" / "program.cps"

TARGET = re.compile(r"(?:goto|try_begin) (L\d+)$")


def assert_well_formed(result):
    """Invariantes que debe cumplir cualquier salida TAC completa."""
    assert result.errors == []
    assert result.emitter.live_temps() == 0
    lines = result.tac
    placed = [line[:-1] for line in lines if re.fullmatch(r"L\d+:", line)]
    assert len(placed) == len(set(placed))
    targets = {match.group(1) for line in lines if (match := TARGET.search(line))}
    assert targets <= set(placed)
    begins = [line.split()[1] for line in lines if line.startswith("begin_func ")]
    ends = [line.split()[1] for line in lines if line.startswith("end_func ")]
    assert begins == ends
    assert begins[0] == "main"
    assert set(begins) == set(result.emitter.function_temps)
    assert set(begins) <= set(result.analyzer.activation_records)
    return lines


def unit(lines, name):
    return lines[lines.index(f"begin_func {name}"):lines.index(f"end_func {name}") + 1]


def test_program_cps_generates_complete_tac():
    result = compile_source(PROGRAM.read_text(encoding="utf-8"))
    lines = assert_well_formed(result)
    units = [line.split()[1] for line in lines if line.startswith("begin_func ")]
    assert units == ["main", "makeAdder", "Animal.constructor", "Animal.speak", "Dog.speak", "getMultiples", "factorial"]
    main = unit(lines, "main")
    assert main[1:4] == ["PI = 314", "greeting = .str0", "flag = false"]
    assert ["t0 = new Dog", "param t0", "param .str13", "call Animal.constructor, 2", "dog = t0"] == \
        main[main.index("t0 = new Dog"):main.index("dog = t0") + 1]
    assert "t0 = call Dog.speak, 1" in main
    assert unit(lines, "factorial")[-4:] == ["t0 = call factorial, 1", "t0 = n_2 * t0", "return t0", "end_func factorial"]


def test_program_cps_runtime_error_and_memory():
    result = compile_source(PROGRAM.read_text(encoding="utf-8"))
    main = unit(result.tac, "main")
    start = main.index("try_begin L19")
    assert main[start:start + 3] == ["try_begin L19", "bounds numbers, 10", "t0 = numbers[10]"]
    assert result.emitter.strings[".str10"] == "indice fuera de rango"
    analyzer = result.analyzer
    assert [(f.name, f.offset) for f in analyzer.class_layouts["Dog"]] == [("name", 0)]
    speak = analyzer.activation_records["Dog.speak"]
    assert [(s.name, s.offset) for s in speak.parameters] == [("this", 12)]
    assert speak.size == 12 + 4 * (1 + result.emitter.function_temps["Dog.speak"])
    record = analyzer.activation_records["getMultiples"]
    assert [(s.name, s.offset, s.storage) for s in record.parameters + record.locals] == [
        ("n", 12, "param"), ("result", 16, "local")]


def test_complete_program_with_every_construct_has_exact_tac():
    source = """
    class Shape {
      let name: string = "shape";
      function area(): integer { return 0; }
    }
    class Square : Shape {
      let side: integer;
      function constructor(side: integer) { this.side = side; }
      function area(): integer { return this.side * this.side; }
    }
    function total(shapes: Square[]): integer {
      let sum = 0;
      foreach (s in shapes) { sum = sum + s.area(); }
      return sum;
    }
    let shapes: Square[] = [new Square(2), new Square(3)];
    try {
      print(total(shapes));
      print(shapes[5].name);
    } catch (e) {
      print(e);
    }
    """
    result = compile_source(source)
    assert assert_well_formed(result) == [
        "begin_func main",
        "t0 = new_array 2",
        "t1 = new Square", "t1.name = .str0", "param t1", "param 2", "call Square.constructor, 2", "t0[0] = t1",
        "t1 = new Square", "t1.name = .str0", "param t1", "param 3", "call Square.constructor, 2", "t0[1] = t1",
        "shapes_1 = t0",
        "try_begin L0",
        "param shapes_1", "t0 = call total, 1", "print t0",
        "bounds shapes_1, 5", "t0 = shapes_1[5]", "t0 = t0.name", "print t0",
        "try_end", "goto L1",
        "L0:", "catch e", "print e", "L1:",
        "end_func main",
        "begin_func Shape.area", "return 0", "end_func Shape.area",
        "begin_func Square.constructor", "this.side = side", "return", "end_func Square.constructor",
        "begin_func Square.area", "t0 = this.side", "t1 = this.side", "t0 = t0 * t1", "return t0", "end_func Square.area",
        "begin_func total",
        "sum = 0",
        "t0 = shapes", "t1 = len t0", "t2 = 0",
        "L2:", "t3 = t2 < t1", "ifFalse t3 goto L4",
        "s = t0[t2]",
        "param s", "t3 = call Square.area, 1", "t3 = sum + t3", "sum = t3",
        "L3:", "t2 = t2 + 1", "goto L2", "L4:",
        "return sum",
        "end_func total",
    ]
    assert result.emitter.strings == {".str0": "shape", ".str1": "indice fuera de rango"}


def test_readme_examples_compile_end_to_end():
    source = """
    function saludar(nombre: string): string { return "Hola " + nombre; }
    let mensaje = saludar("Mundo");
    function crearContador(): integer {
      function siguiente(): integer { return 1; }
      return siguiente();
    }
    let lista = [1, 2, 3];
    try { let peligro = lista[100]; } catch (err) { print("Error atrapado: " + err); }
    let notas: integer[] = [90, 85, 100];
    foreach (n in notas) { if (n < 60) { continue; } if (n == 100) { break; } print(n); }
    let x = 5;
    switch (x) { case 1: print("uno"); case 2: print("dos"); default: print("otro"); }
    let y = !(x < 10 || x > 20);
    """
    lines = assert_well_formed(compile_source(source))
    assert "t0 = call crearContador.siguiente, 0" in lines


@pytest.mark.parametrize("source", [
    "class A { let x: integer; } let a: A = new A(); a.y = 1;",
    "let a = [1, 2]; foreach (x in a) { x = true; }",
    "class A { function f(): integer { return true; } }",
    "let a: integer[] = [1]; let b: string = a[0];",
])
def test_invalid_complete_programs_generate_no_tac(source):
    result = compile_source(source)
    assert result.errors
    assert result.tac == []


def test_driver_prints_tac_for_program_cps(capsys):
    from program.Driver import main
    main(["Driver.py", str(PROGRAM)])
    output = capsys.readouterr().out
    assert output.startswith(".data\n    .str0: \"Hello, Compiscript!\"")
    assert "\n.code\n    begin_func main\n" in output
    assert "    call Animal.constructor, 2" in output


def test_driver_reports_semantic_errors(tmp_path, capsys):
    from program.Driver import main
    source = tmp_path / "bad.cps"
    source.write_text("let x: integer = true;", encoding="utf-8")
    with pytest.raises(SystemExit) as exit_info:
        main(["Driver.py", str(source)])
    assert exit_info.value.code == 1
    assert "asignacion-tipo-incompatible" in capsys.readouterr().err


def test_ide_compiles_program_cps():
    app = create_app()
    app.config.update(TESTING=True)
    payload = app.test_client().post("/compile", json={"source": PROGRAM.read_text(encoding="utf-8")}).get_json()
    assert payload["success"] is True
    assert payload["tacError"] is None
    assert payload["tac"][0] == "begin_func main"
    frames = {frame["name"]: frame for frame in payload["activationRecords"]}
    assert frames["Animal.constructor"]["parameters"] == [{"name": "this", "offset": 12}, {"name": "name", "offset": 16}]
    fields = {(s["name"], s["storage"], s["offset"]) for s in payload["symbols"] if s["storage"] == "field"}
    assert fields == {("name", "field", 0)}
