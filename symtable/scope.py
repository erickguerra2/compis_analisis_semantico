from __future__ import annotations

from enum import Enum, auto
from typing import Dict, Optional

from .errors import DuplicateSymbolError
from .symbol import Symbol


class ScopeKind(Enum):
    GLOBAL = auto()
    BLOCK = auto()
    FUNCTION = auto()
    CLASS = auto()


class Scope:
    def __init__(self, kind: ScopeKind, parent: Optional["Scope"] = None):
        self.kind = kind
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}

    def declare(self, symbol: Symbol) -> None:
        if symbol.name in self.symbols:
            raise DuplicateSymbolError(symbol.name)
        symbol.scope = self
        self.symbols[symbol.name] = symbol

    def resolve_local(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name)

    def resolve(self, name: str) -> Optional[Symbol]:
        scope: Optional[Scope] = self
        while scope is not None:
            symbol = scope.resolve_local(name)
            if symbol is not None:
                return symbol
            scope = scope.parent
        return None
