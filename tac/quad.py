from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Union


class Operand:
    pass


@dataclass(frozen=True)
class Var(Operand):
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Temp(Operand):
    id: int

    def __str__(self) -> str:
        return f"t{self.id}"


@dataclass(frozen=True)
class Const(Operand):
    value: Any

    def __str__(self) -> str:
        if self.value is True:
            return "true"
        if self.value is False:
            return "false"
        if self.value is None:
            return "null"
        return str(self.value)


@dataclass(frozen=True)
class StrLit(Operand):
    label: str

    def __str__(self) -> str:
        return self.label


@dataclass(frozen=True)
class Label(Operand):
    name: str

    def __str__(self) -> str:
        return self.name


Value = Union[Operand, str, int, bool]


@dataclass
class Quad:
    op: str
    arg1: Optional[Value] = None
    arg2: Optional[Value] = None
    result: Optional[Value] = None

    def __str__(self) -> str:
        a1, a2, result = map(lambda value: "" if value is None else str(value), (self.arg1, self.arg2, self.result))
        if self.op in {"+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!="}:
            return f"{result} = {a1} {self.op} {a2}"
        if self.op in {"neg", "not", "len", "to_str", "new", "new_array"}:
            return f"{result} = {self.op} {a1}"
        if self.op == "concat":
            return f"{result} = concat {a1}, {a2}"
        if self.op == "copy":
            return f"{result} = {a1}"
        if self.op == "label":
            return f"{result}:"
        if self.op == "goto":
            return f"goto {result}"
        if self.op in {"if", "ifFalse"}:
            return f"{self.op} {a1} goto {result}"
        if self.op in {"begin_func", "end_func", "param", "return", "print", "throw", "catch", "try_begin"}:
            return self.op if a1 == "" else f"{self.op} {a1}"
        if self.op == "try_end":
            return "try_end"
        if self.op == "call":
            call = f"call {a1}, {a2}"
            return call if self.result is None else f"{result} = {call}"
        if self.op == "bounds":
            return f"bounds {a1}, {a2}"
        if self.op == "index_load":
            return f"{result} = {a1}[{a2}]"
        if self.op == "index_store":
            return f"{result}[{a1}] = {a2}"
        if self.op == "field_load":
            return f"{result} = {a1}.{a2}"
        if self.op == "field_store":
            return f"{result}.{a1} = {a2}"
        raise ValueError(f"opcode TAC desconocido: {self.op}")
