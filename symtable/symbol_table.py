from __future__ import annotations

from typing import Optional, Set

from .errors import DuplicateSymbolError
from .scope import Scope, ScopeKind
from .symbol import Symbol, SymbolCategory


class SymbolTable:
    def __init__(self):
        self._global_scope = Scope(ScopeKind.GLOBAL)
        self._scope_stack = [self._global_scope]
        self._all_scopes = [self._global_scope]

    @property
    def current_scope(self) -> Scope:
        return self._scope_stack[-1]

    @property
    def global_scope(self) -> Scope:
        return self._global_scope

    @property
    def scopes(self):
        return tuple(self._all_scopes)

    def enter_scope(self, kind: ScopeKind) -> Scope:
        scope = Scope(kind, parent=self.current_scope)
        self._scope_stack.append(scope)
        self._all_scopes.append(scope)
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

    def resolve_class(self, name: str, from_scope: Optional[Scope] = None) -> Optional[Symbol]:
        """Resuelve una clase visible desde el ambito indicado."""
        symbol = (from_scope or self.current_scope).resolve(name)
        if symbol is not None and symbol.category is SymbolCategory.CLASS:
            return symbol
        return None

    def resolve_member(self, class_name: str, member_name: str) -> Optional[Symbol]:
        """Busca un miembro propio o heredado sin mezclar el ambito lexico."""
        class_symbol = self.resolve_class(class_name)
        visited: Set[str] = set()

        while class_symbol is not None and class_symbol.name not in visited:
            visited.add(class_symbol.name)
            if class_symbol.class_scope is not None:
                member = class_symbol.class_scope.resolve_local(member_name)
                if member is not None:
                    return member
            if class_symbol.parent_class is None:
                break
            class_symbol = self.resolve_class(class_symbol.parent_class, class_symbol.scope)
        return None
