from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from semantic.types import Type

    from .scope import Scope


class SymbolCategory(Enum):
    VARIABLE = auto()
    CONSTANT = auto()
    FUNCTION = auto()
    PARAMETER = auto()
    CLASS = auto()


@dataclass
class Symbol:
    name: str
    category: SymbolCategory
    type: Optional["Type"] = None
    initialized: bool = False
    scope: Optional["Scope"] = None
    params: Optional[List["Type"]] = None
    return_type: Optional["Type"] = None
    parent_class: Optional[str] = None
    class_scope: Optional["Scope"] = None
