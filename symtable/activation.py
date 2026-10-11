from __future__ import annotations

from dataclasses import dataclass, field

from semantic.types import size_of
from .scope import ScopeKind
from .symbol import SymbolCategory


@dataclass
class ActivationRecord:
    name: str
    depth: int = 0
    access_parent: str | None = None
    parameters: list = field(default_factory=list)
    locals: list = field(default_factory=list)
    ntemporals: int = 0
    return_address_offset: int = 0
    control_link_offset: int = 4
    access_link_offset: int = 8

    @property
    def temporaries_offset(self):
        return 12 + 4 * (len(self.parameters) + len(self.locals))

    def temp_offset(self, id_):
        if not 0 <= id_ < self.ntemporals:
            raise IndexError("temporal fuera del registro")
        return self.temporaries_offset + 4 * id_

    @property
    def size(self):
        return self.temporaries_offset + 4 * self.ntemporals


class MemoryLayout:
    """Asigna memoria sin reutilizar slots entre bloques hermanos."""
    def __init__(self, analyzer, tree):
        self.analyzer = analyzer
        self.functions = {}
        self.records = {"main": ActivationRecord("main")}
        self.scope_functions = {}
        self.declaration_order = {}
        self._collect(tree)
        for ctx, symbol, scope in self.functions.values():
            parent = self._owner(scope.parent)
            class_owner = next((s for s in analyzer.symbol_table.scopes
                                if s.kind is ScopeKind.CLASS and s is scope.parent), None)
            if parent is not None:
                parent_record = self.records[parent.label]
                symbol.label = parent.label + "." + symbol.name
                depth = parent_record.depth + 1
            else:
                class_symbol = next((s for sc in analyzer.symbol_table.scopes
                                     for s in sc.symbols.values()
                                     if s.class_scope is class_owner), None) if class_owner else None
                symbol.label = (class_symbol.name + "." if class_symbol else "") + symbol.name
                depth = 1
            symbol.depth = depth - 1
            record = ActivationRecord(symbol.label, depth, parent.label if parent else None)
            if class_owner:
                from .symbol import Symbol
                from semantic.types import ClassType
                record.parameters.append(Symbol("this", SymbolCategory.PARAMETER,
                                                ClassType(class_symbol.name), True,
                                                offset=12, size=4, storage="param", depth=depth))
            self.records[symbol.label] = record
        global_count = 0
        symbols = [(scope, symbol) for scope in analyzer.symbol_table.scopes
                   for symbol in scope.symbols.values()]
        symbols.sort(key=lambda item: self.declaration_order.get(id(item[1]), float("inf")))
        for scope, symbol in symbols:
            owner = self._owner(scope)
            if symbol.category not in {SymbolCategory.VARIABLE, SymbolCategory.CONSTANT, SymbolCategory.PARAMETER}:
                continue
            symbol.size = size_of(symbol.type)
            if scope.kind is ScopeKind.CLASS:
                symbol.storage = "field"
                continue  # Herencia y offsets de campos corresponden al turno 4.
            if owner is None:
                symbol.storage, symbol.depth = "global", 0
                symbol.offset = 4 * global_count
                global_count += 1
            else:
                record = self.records[owner.label]
                symbol.depth = record.depth
                if symbol.category is SymbolCategory.PARAMETER:
                    symbol.storage = "param"
                    symbol.offset = 12 + 4 * len(record.parameters)
                    record.parameters.append(symbol)
                else:
                    symbol.storage = "local"
                    record.locals.append(symbol)
        for record in self.records.values():
            for i, symbol in enumerate(record.locals):
                symbol.offset = 12 + 4 * (len(record.parameters) + i)
        analyzer.activation_records = self.records

    def _collect(self, ctx):
        from generated.CompiscriptParser import CompiscriptParser
        annotation = self.analyzer.annotation_of(ctx)
        if annotation and annotation.symbol and hasattr(ctx, "start"):
            key = id(annotation.symbol)
            self.declaration_order[key] = min(self.declaration_order.get(key, ctx.start.tokenIndex), ctx.start.tokenIndex)
        if isinstance(ctx, CompiscriptParser.FunctionDeclarationContext):
            symbol = self.analyzer.annotation_of(ctx).symbol
            scope = self.analyzer.annotation_of(ctx.block()).scope
            self.functions[id(ctx)] = (ctx, symbol, scope)
            self.scope_functions[id(scope)] = symbol
        for child in getattr(ctx, "children", None) or []:
            self._collect(child)

    def _owner(self, scope):
        while scope is not None:
            if id(scope) in self.scope_functions:
                return self.scope_functions[id(scope)]
            scope = scope.parent
        return None

    def finalize(self, emitter):
        for name, count in emitter.function_temps.items():
            self.records[name].ntemporals = count
