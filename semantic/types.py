from __future__ import annotations

from typing import List, Optional, Tuple


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
        return_name = self.return_type.name if self.return_type is not None else "void"
        return f"({params}) -> {return_name}"


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


def is_numeric(candidate) -> bool:
    return isinstance(candidate, (IntegerType, FloatType))


def is_boolean(candidate) -> bool:
    return isinstance(candidate, BooleanType)


def numeric_result(left: Type, right: Type) -> Type:
    return FLOAT if isinstance(left, FloatType) or isinstance(right, FloatType) else INTEGER


def comparable_for_equality(left, right) -> bool:
    if left is None or right is None:
        return True
    if left == right:
        return True
    if is_numeric(left) and is_numeric(right):
        return True
    if isinstance(left, NullType) or isinstance(right, NullType):
        return True
    return False


def is_assignable(target: Optional[Type], value: Optional[Type]) -> bool:
    """Determina si un valor de tipo `value` puede asignarse a algo de tipo `target`."""
    if target is None or value is None:
        return True
    if target == value:
        return True
    if isinstance(target, FloatType) and isinstance(value, IntegerType):
        return True
    if isinstance(target, (ClassType, ArrayType)) and isinstance(value, NullType):
        return True
    if isinstance(target, ArrayType) and isinstance(value, ArrayType) and isinstance(value.base, NullType):
        return True
    return False
