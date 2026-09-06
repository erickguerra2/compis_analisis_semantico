from __future__ import annotations

from typing import List, Tuple


class Type:
    name = "type"

    def _key(self) -> Tuple:
        return ()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self)) and self._key() == other._key()

    def __hash__(self) -> int:
        return hash((type(self), self._key()))

    def __repr__(self) -> str:
        return self.name


class IntegerType(Type):
    name = "integer"


class FloatType(Type):
    name = "float"


class StringType(Type):
    name = "string"


class BooleanType(Type):
    name = "boolean"


class NullType(Type):
    name = "null"


class VoidType(Type):
    name = "void"


class ClassType(Type):
    def __init__(self, class_name: str):
        self.class_name = class_name

    def _key(self) -> Tuple:
        return (self.class_name,)

    @property
    def name(self) -> str:
        return self.class_name


class ArrayType(Type):
    def __init__(self, base: Type, dimensions: int = 1):
        self.base = base
        self.dimensions = dimensions

    def _key(self) -> Tuple:
        return (self.base, self.dimensions)

    @property
    def name(self) -> str:
        return self.base.name + "[]" * self.dimensions


class FunctionType(Type):
    def __init__(self, params: List[Type], return_type: Type):
        self.params = params
        self.return_type = return_type

    def _key(self) -> Tuple:
        return (tuple(self.params), self.return_type)

    @property
    def name(self) -> str:
        params = ", ".join(param.name for param in self.params)
        return f"({params}) -> {self.return_type.name}"


INTEGER = IntegerType()
FLOAT = FloatType()
STRING = StringType()
BOOLEAN = BooleanType()
NULL = NullType()
VOID = VoidType()

_BASE_TYPES = {
    "integer": INTEGER,
    "float": FLOAT,
    "string": STRING,
    "boolean": BOOLEAN,
}


def resolve_base_type(name: str) -> Type:
    return _BASE_TYPES.get(name, ClassType(name))
