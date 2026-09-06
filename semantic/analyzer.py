from __future__ import annotations

from typing import Optional

from generated.CompiscriptParser import CompiscriptParser
from generated.CompiscriptVisitor import CompiscriptVisitor

from symtable.scope import ScopeKind
from symtable.symbol import Symbol, SymbolCategory
from symtable.symbol_table import SymbolTable

from .errors import ErrorReporter
from .types import ArrayType, FunctionType, Type, resolve_base_type


class SemanticAnalyzer(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.errors = ErrorReporter()

    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        for statement in ctx.statement():
            self.visit(statement)
        return None

    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        self.symbol_table.enter_scope(ScopeKind.BLOCK)
        for statement in ctx.statement():
            self.visit(statement)
        self.symbol_table.exit_scope()
        return None

    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        symbol = Symbol(
            name=ctx.Identifier().getText(),
            category=SymbolCategory.VARIABLE,
            type=self._optional_type(ctx.typeAnnotation()),
            initialized=ctx.initializer() is not None,
        )
        self._declare(symbol, ctx)
        if ctx.initializer() is not None:
            self.visit(ctx.initializer())
        return None

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        symbol = Symbol(
            name=ctx.Identifier().getText(),
            category=SymbolCategory.CONSTANT,
            type=self._optional_type(ctx.typeAnnotation()),
            initialized=True,
        )
        self._declare(symbol, ctx)
        self.visit(ctx.expression())
        return None

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        param_ctxs = ctx.parameters().parameter() if ctx.parameters() else []
        param_types = [self._optional_type(param_ctx) for param_ctx in param_ctxs]
        return_type = self._optional_type(ctx)

        function_symbol = Symbol(
            name=ctx.Identifier().getText(),
            category=SymbolCategory.FUNCTION,
            type=FunctionType(param_types, return_type),
            initialized=True,
            params=param_types,
            return_type=return_type,
        )
        self._declare(function_symbol, ctx)

        self.symbol_table.enter_scope(ScopeKind.FUNCTION)
        for param_ctx, param_type in zip(param_ctxs, param_types):
            parameter_symbol = Symbol(
                name=param_ctx.Identifier().getText(),
                category=SymbolCategory.PARAMETER,
                type=param_type,
                initialized=True,
            )
            self._declare(parameter_symbol, param_ctx)
        for statement in ctx.block().statement():
            self.visit(statement)
        self.symbol_table.exit_scope()
        return None

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        identifiers = ctx.Identifier()
        name = identifiers[0].getText()
        parent_class = identifiers[1].getText() if len(identifiers) > 1 else None

        class_symbol = Symbol(
            name=name,
            category=SymbolCategory.CLASS,
            type=resolve_base_type(name),
            initialized=True,
            parent_class=parent_class,
        )
        self._declare(class_symbol, ctx)

        class_symbol.class_scope = self.symbol_table.enter_scope(ScopeKind.CLASS)
        for member in ctx.classMember():
            self.visit(member)
        self.symbol_table.exit_scope()
        return None

    def visitIdentifierExpr(self, ctx: CompiscriptParser.IdentifierExprContext):
        name = ctx.Identifier().getText()
        symbol = self.symbol_table.resolve(name)
        if symbol is None:
            token = ctx.Identifier().getSymbol()
            self.errors.report(
                token.line,
                token.column,
                f"variable '{name}' no declarada",
                "uso-variable-no-declarada",
            )
            return None
        return symbol.type

    def _declare(self, symbol: Symbol, ctx) -> None:
        error = self.symbol_table.declare(symbol)
        if error is not None:
            token = ctx.start
            self.errors.report(
                token.line,
                token.column,
                str(error),
                "redeclaracion-mismo-ambito",
            )

    def _optional_type(self, ctx) -> Optional[Type]:
        if ctx is None:
            return None
        type_ctx = ctx.type_()
        if type_ctx is None:
            return None
        base = resolve_base_type(type_ctx.baseType().getText())
        dimensions = type_ctx.getText().count("[")
        return ArrayType(base, dimensions) if dimensions else base
