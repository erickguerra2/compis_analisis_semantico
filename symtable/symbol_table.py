from __future__ import annotations

from typing import Optional

from .errors import DuplicateSymbolError
from .scope import Scope, ScopeKind
from .symbol import Symbol


class SymbolTable:
    def __init__(self):
        self._global_scope = Scope(ScopeKind.GLOBAL)
        self._scope_stack = [self._global_scope]

    @property
    def current_scope(self) -> Scope:
        return self._scope_stack[-1]

    @property
    def global_scope(self) -> Scope:
        return self._global_scope

    def enter_scope(self, kind: ScopeKind) -> Scope:
        scope = Scope(kind, parent=self.current_scope)
        self._scope_stack.append(scope)
        return scope

    def exit_scope(self) -> Scope:
        return self._scope_stack.pop()

    def declare(self, symbol: Symbol) -> Optional[DuplicateSymbolError]:
        try:
            self.current_scope.declare(symbol)
            return None
        except DuplicateSymbolError as error:
            return error

    def resolve(self, name: str) -> Optional[Symbol]:
        return self.current_scope.resolve(name)
