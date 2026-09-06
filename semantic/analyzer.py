from __future__ import annotations

from typing import Optional

from generated.CompiscriptParser import CompiscriptParser
from generated.CompiscriptVisitor import CompiscriptVisitor

from symtable.scope import ScopeKind
from symtable.symbol import Symbol, SymbolCategory
from symtable.symbol_table import SymbolTable

from .errors import ErrorReporter
from .types import (
    BOOLEAN,
    INTEGER,
    NULL,
    STRING,
    ArrayType,
    FunctionType,
    IntegerType,
    Type,
    comparable_for_equality,
    is_boolean,
    is_numeric,
    numeric_result,
    resolve_base_type,
)


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

    def visitTernaryExpr(self, ctx: CompiscriptParser.TernaryExprContext):
        condition_type = self.visit(ctx.logicalOrExpr())
        branches = ctx.expression()
        if not branches:
            return condition_type
        self._expect_boolean(condition_type, ctx.logicalOrExpr().start, "el operador ternario '?:'")
        then_type = self.visit(branches[0])
        else_type = self.visit(branches[1])
        if then_type is not None and else_type is not None and then_type != else_type:
            return None
        return then_type if then_type is not None else else_type

    def visitLogicalOrExpr(self, ctx: CompiscriptParser.LogicalOrExprContext):
        operands = ctx.logicalAndExpr()
        result = self.visit(operands[0])
        for i in range(1, len(operands)):
            right = self.visit(operands[i])
            self._require_boolean_operand(result, operands[i - 1], "||")
            self._require_boolean_operand(right, operands[i], "||")
            result = BOOLEAN
        return result

    def visitLogicalAndExpr(self, ctx: CompiscriptParser.LogicalAndExprContext):
        operands = ctx.equalityExpr()
        result = self.visit(operands[0])
        for i in range(1, len(operands)):
            right = self.visit(operands[i])
            self._require_boolean_operand(result, operands[i - 1], "&&")
            self._require_boolean_operand(right, operands[i], "&&")
            result = BOOLEAN
        return result

    def visitEqualityExpr(self, ctx: CompiscriptParser.EqualityExprContext):
        operands = ctx.relationalExpr()
        if len(operands) == 1:
            return self.visit(operands[0])
        previous_type = self.visit(operands[0])
        for i in range(1, len(operands)):
            current_type = self.visit(operands[i])
            operator = ctx.getChild(2 * i - 1).getText()
            if previous_type is not None and current_type is not None and not comparable_for_equality(
                previous_type, current_type
            ):
                token = operands[i].start
                self.errors.report(
                    token.line,
                    token.column,
                    f"no se pueden comparar tipos '{previous_type.name}' y '{current_type.name}' con '{operator}'",
                    "comparacion-tipos-incompatibles",
                )
            previous_type = current_type
        return BOOLEAN

    def visitRelationalExpr(self, ctx: CompiscriptParser.RelationalExprContext):
        operands = ctx.additiveExpr()
        if len(operands) == 1:
            return self.visit(operands[0])
        previous_type = self.visit(operands[0])
        for i in range(1, len(operands)):
            current_type = self.visit(operands[i])
            operator = ctx.getChild(2 * i - 1).getText()
            self._require_numeric_operand(previous_type, operands[i - 1], operator, "operador-relacional-tipo-invalido")
            self._require_numeric_operand(current_type, operands[i], operator, "operador-relacional-tipo-invalido")
            previous_type = current_type
        return BOOLEAN

    def visitAdditiveExpr(self, ctx: CompiscriptParser.AdditiveExprContext):
        return self._check_left_associative_arithmetic(ctx, ctx.multiplicativeExpr())

    def visitMultiplicativeExpr(self, ctx: CompiscriptParser.MultiplicativeExprContext):
        return self._check_left_associative_arithmetic(ctx, ctx.unaryExpr())

    def _check_left_associative_arithmetic(self, ctx, operands):
        result = self.visit(operands[0])
        for i in range(1, len(operands)):
            right = self.visit(operands[i])
            operator = ctx.getChild(2 * i - 1).getText()
            self._require_numeric_operand(result, operands[i - 1], operator)
            self._require_numeric_operand(right, operands[i], operator)
            result = numeric_result(result, right) if is_numeric(result) and is_numeric(right) else None
        return result

    def visitUnaryExpr(self, ctx: CompiscriptParser.UnaryExprContext):
        if ctx.unaryExpr() is not None:
            operand_type = self.visit(ctx.unaryExpr())
            operator = ctx.getChild(0).getText()
            if operator == "-":
                self._require_numeric_operand(operand_type, ctx.unaryExpr(), operator, "operador-unario-tipo-invalido")
                return operand_type if is_numeric(operand_type) else None
            self._require_boolean_operand(operand_type, ctx.unaryExpr(), operator, "operador-unario-tipo-invalido")
            return BOOLEAN
        return self.visit(ctx.primaryExpr())

    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        return self.visit(ctx.expression())

    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext):
        if ctx.Literal() is not None:
            text = ctx.Literal().getText()
            return STRING if text.startswith('"') else INTEGER
        if ctx.arrayLiteral() is not None:
            return self.visit(ctx.arrayLiteral())
        if ctx.getText() == "null":
            return NULL
        return BOOLEAN

    def visitArrayLiteral(self, ctx: CompiscriptParser.ArrayLiteralContext):
        element_ctxs = ctx.expression()
        element_types = [self.visit(element_ctx) for element_ctx in element_ctxs]
        known_types = [element_type for element_type in element_types if element_type is not None]
        if not known_types:
            return ArrayType(NULL, 1)

        first = known_types[0]
        for element_ctx, element_type in zip(element_ctxs, element_types):
            if element_type is None:
                continue
            if element_type != first and not (is_numeric(element_type) and is_numeric(first)):
                token = element_ctx.start
                self.errors.report(
                    token.line,
                    token.column,
                    f"los elementos del arreglo deben ser del mismo tipo: se esperaba "
                    f"'{first.name}' y se encontro '{element_type.name}'",
                    "arreglo-tipos-inconsistentes",
                )

        if is_numeric(first):
            base = first
            for element_type in known_types:
                if is_numeric(element_type):
                    base = numeric_result(base, element_type)
            return ArrayType(base, 1)
        return ArrayType(first, 1)

    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        current_type = self.visit(ctx.primaryAtom())
        for suffix in ctx.suffixOp():
            current_type = self._apply_suffix(current_type, suffix)
        return current_type

    def _apply_suffix(self, base_type: Optional[Type], suffix_ctx):
        if isinstance(suffix_ctx, CompiscriptParser.IndexExprContext):
            index_type = self.visit(suffix_ctx.expression())
            if index_type is not None and not isinstance(index_type, IntegerType):
                token = suffix_ctx.expression().start
                self.errors.report(
                    token.line,
                    token.column,
                    f"el indice de un arreglo debe ser de tipo integer, se encontro '{index_type.name}'",
                    "indice-no-entero",
                )
            if base_type is None:
                return None
            if not isinstance(base_type, ArrayType):
                token = suffix_ctx.start
                self.errors.report(
                    token.line,
                    token.column,
                    f"no se puede indexar un valor de tipo '{base_type.name}'",
                    "indice-sobre-no-arreglo",
                )
                return None
            if base_type.dimensions > 1:
                return ArrayType(base_type.base, base_type.dimensions - 1)
            return base_type.base
        if isinstance(suffix_ctx, CompiscriptParser.CallExprContext):
            if suffix_ctx.arguments() is not None:
                self.visit(suffix_ctx.arguments())
            return None
        # PropertyAccessExpr: la resolucion de miembros de clase (incluida herencia)
        # es responsabilidad de la seccion 3.5, todavia no implementada.
        return None

    def _expect_boolean(self, type_: Optional[Type], token, context_label: str) -> None:
        if type_ is not None and not is_boolean(type_):
            self.errors.report(
                token.line,
                token.column,
                f"la condicion de {context_label} debe ser de tipo boolean, se encontro '{type_.name}'",
                "condicion-no-booleana",
            )

    def _require_numeric_operand(self, type_: Optional[Type], ctx, operator: str, rule: str = "operador-aritmetico-tipo-invalido") -> None:
        if type_ is not None and not is_numeric(type_):
            token = ctx.start
            self.errors.report(
                token.line,
                token.column,
                f"el operador '{operator}' requiere operandos numericos (integer/float), se encontro '{type_.name}'",
                rule,
            )

    def _require_boolean_operand(self, type_: Optional[Type], ctx, operator: str, rule: str = "operador-logico-tipo-invalido") -> None:
        if type_ is not None and not is_boolean(type_):
            token = ctx.start
            self.errors.report(
                token.line,
                token.column,
                f"el operador '{operator}' requiere operandos de tipo boolean, se encontro '{type_.name}'",
                rule,
            )

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
