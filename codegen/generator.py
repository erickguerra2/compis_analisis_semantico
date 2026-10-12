from __future__ import annotations

from generated.CompiscriptVisitor import CompiscriptVisitor

from tac import Emitter, Var

from .classes import ClassesMixin
from .control_flow import ControlFlowMixin
from .expressions import ExpressionsMixin
from .functions import FunctionsMixin
from symtable.activation import MemoryLayout
from symtable.symbol import SymbolCategory
from symtable.scope import ScopeKind


class UnsupportedConstructionsMixin:
    def _unsupported(self, ctx):
        raise NotImplementedError("construcción no soportada todavía")

    visitFunctionDeclaration = _unsupported
    visitForeachStatement = _unsupported
    visitReturnStatement = _unsupported


class TacGenerator(ClassesMixin, FunctionsMixin, ExpressionsMixin, ControlFlowMixin, UnsupportedConstructionsMixin, CompiscriptVisitor):
    def __init__(self, analyzer, tree):
        self.analyzer = analyzer
        self.tree = tree
        self.emitter = Emitter()
        self.loop_stack = []
        self.try_depth = 0
        self.pending = []
        self.class_declarations = {}
        self._symbol_vars = {}
        self._name_counts = {}

    def generate(self):
        if self.analyzer.errors.has_errors():
            return self.emitter
        layout = MemoryLayout(self.analyzer, self.tree)
        # El orden fuente incluye par?metros y declaraciones de cuerpos pendientes.
        declarations = []
        def collect(ctx):
            annotation = self._annotation(ctx)
            if annotation and annotation.symbol and annotation.symbol.category in {
                SymbolCategory.VARIABLE, SymbolCategory.CONSTANT, SymbolCategory.PARAMETER
            } and annotation.symbol.scope.kind is not ScopeKind.CLASS:
                declarations.append((ctx.start.tokenIndex, annotation.symbol))
            for child in getattr(ctx, "children", None) or []:
                if hasattr(child, "getRuleIndex"):
                    collect(child)
        collect(self.tree)
        for _, symbol in sorted(declarations, key=lambda item: item[0]):
            self._var_for_symbol(symbol)
        self.emitter.begin_function("main")
        for statement in self.tree.statement():
            self.visit(statement)
        self.emitter.end_function("main")
        while self.pending:
            self._emit_function(self.pending.pop(0))
        layout.finalize(self.emitter)
        return self.emitter

    def _annotation(self, ctx):
        return self.analyzer.annotation_of(ctx)

    def _type_of(self, ctx):
        annotation = self._annotation(ctx)
        return annotation.type if annotation is not None else None

    def _symbol_of(self, ctx):
        annotation = self._annotation(ctx)
        return annotation.symbol if annotation is not None else None

    def _declare_var(self, ctx):
        symbol = self._symbol_of(ctx)
        return self._var_for_symbol(symbol)

    def _var_for_symbol(self, symbol):
        if symbol is None:
            raise RuntimeError("falta anotación de símbolo para generar TAC")
        key = id(symbol)
        if key not in self._symbol_vars:
            count = self._name_counts.get(symbol.name, 0)
            name = symbol.name if count == 0 else f"{symbol.name}_{count}"
            self._name_counts[symbol.name] = count + 1
            self._symbol_vars[key] = Var(name)
        return self._symbol_vars[key]

    def gen_index(self, base, index_ctx, ctx):
        raise NotImplementedError("construcción no soportada todavía")

    def gen_array_literal(self, ctx):
        raise NotImplementedError("construcción no soportada todavía")

    def gen_index_store(self, base, index_ctx, value, ctx):
        raise NotImplementedError("construcción no soportada todavía")
