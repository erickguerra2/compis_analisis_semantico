from __future__ import annotations

from typing import List, Optional

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
    VOID,
    ArrayType,
    ClassType,
    FunctionType,
    IntegerType,
    Type,
    comparable_for_equality,
    is_assignable,
    is_boolean,
    is_numeric,
    numeric_result,
    resolve_base_type,
)


class SemanticAnalyzer(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.errors = ErrorReporter()
        self._loop_depth = 0
        self._switch_depth = 0
        self._function_return_stack: List[Optional[Type]] = []
        self._class_stack: List[Symbol] = []
        self._this_class_stack: List[Symbol] = []
        self._predeclared_class_members = {}

    def visitProgram(self, ctx: CompiscriptParser.ProgramContext):
        for statement in ctx.statement():
            self.visit(statement)
        return None

    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        self.symbol_table.enter_scope(ScopeKind.BLOCK)
        self._visit_statements_detecting_dead_code(ctx.statement())
        self.symbol_table.exit_scope()
        return None

    def _visit_statements_detecting_dead_code(self, statements) -> None:
        already_reported = False
        block_has_terminated = False
        for statement in statements:
            if block_has_terminated and not already_reported:
                token = statement.start
                self.errors.report(
                    token.line,
                    token.column,
                    "codigo inalcanzable: hay instrucciones despues de un 'return'/'break'/'continue' "
                    "en el mismo bloque",
                    "codigo-muerto",
                )
                already_reported = True
            self.visit(statement)
            if self._terminates_block(statement):
                block_has_terminated = True

    def _terminates_block(self, ctx: CompiscriptParser.StatementContext) -> bool:
        return (
            ctx.returnStatement() is not None
            or ctx.breakStatement() is not None
            or ctx.continueStatement() is not None
        )

    def visitIfStatement(self, ctx: CompiscriptParser.IfStatementContext):
        condition_type = self.visit(ctx.expression())
        self._expect_boolean(condition_type, ctx.expression().start, "'if'")
        for block in ctx.block():
            self.visit(block)
        return None

    def visitWhileStatement(self, ctx: CompiscriptParser.WhileStatementContext):
        condition_type = self.visit(ctx.expression())
        self._expect_boolean(condition_type, ctx.expression().start, "'while'")
        self._loop_depth += 1
        self.visit(ctx.block())
        self._loop_depth -= 1
        return None

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        self._loop_depth += 1
        self.visit(ctx.block())
        self._loop_depth -= 1
        condition_type = self.visit(ctx.expression())
        self._expect_boolean(condition_type, ctx.expression().start, "'do-while'")
        return None

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        # El encabezado del for no crea su propio ambito: la variable declarada
        # ahi queda en el ambito contenedor (decision pendiente de ratificar por
        # el equipo, ver plan_tareas_analisis_semantico.md).
        if ctx.variableDeclaration() is not None:
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment() is not None:
            self.visit(ctx.assignment())

        middle_semicolon_index = next(
            index for index in range(3, ctx.getChildCount()) if ctx.getChild(index).getText() == ";"
        )
        condition_ctx = ctx.getChild(3) if middle_semicolon_index != 3 else None
        increment_index = middle_semicolon_index + 1
        increment_ctx = ctx.getChild(increment_index) if ctx.getChild(increment_index).getText() != ")" else None

        if condition_ctx is not None:
            condition_type = self.visit(condition_ctx)
            self._expect_boolean(condition_type, condition_ctx.start, "'for'")
        if increment_ctx is not None:
            self.visit(increment_ctx)

        self._loop_depth += 1
        self._visit_statements_detecting_dead_code(ctx.block().statement())
        self._loop_depth -= 1
        return None

    def visitForeachStatement(self, ctx: CompiscriptParser.ForeachStatementContext):
        iterable_type = self.visit(ctx.expression())
        element_type = iterable_type.base if isinstance(iterable_type, ArrayType) else None

        self.symbol_table.enter_scope(ScopeKind.BLOCK)
        loop_symbol = Symbol(
            name=ctx.Identifier().getText(),
            category=SymbolCategory.VARIABLE,
            type=element_type,
            initialized=True,
        )
        self._declare(loop_symbol, ctx)
        self._loop_depth += 1
        self._visit_statements_detecting_dead_code(ctx.block().statement())
        self._loop_depth -= 1
        self.symbol_table.exit_scope()
        return None

    def visitBreakStatement(self, ctx: CompiscriptParser.BreakStatementContext):
        if self._loop_depth == 0 and self._switch_depth == 0:
            token = ctx.start
            self.errors.report(
                token.line,
                token.column,
                "'break' solo es valido dentro de un bucle o un 'switch'",
                "break-fuera-de-bucle",
            )
        return None

    def visitContinueStatement(self, ctx: CompiscriptParser.ContinueStatementContext):
        if self._loop_depth == 0:
            token = ctx.start
            self.errors.report(
                token.line, token.column, "'continue' solo es valido dentro de un bucle", "continue-fuera-de-bucle"
            )
        return None

    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        value_type = self.visit(ctx.expression()) if ctx.expression() is not None else VOID
        if not self._function_return_stack:
            token = ctx.start
            self.errors.report(
                token.line, token.column, "'return' solo es valido dentro de una funcion", "return-fuera-de-funcion"
            )
            return None
        expected_type = self._function_return_stack[-1]
        if expected_type is not None and value_type is not None and not self._is_assignable(expected_type, value_type):
            token = ctx.start
            self.errors.report(
                token.line,
                token.column,
                f"el tipo de retorno '{value_type.name}' no coincide con el tipo declarado "
                f"'{expected_type.name}'",
                "return-tipo-incompatible",
            )
        return None

    def visitSwitchStatement(self, ctx: CompiscriptParser.SwitchStatementContext):
        subject_type = self.visit(ctx.expression())
        self._switch_depth += 1
        for switch_case in ctx.switchCase():
            case_type = self.visit(switch_case.expression())
            if subject_type is not None and case_type is not None and not self._comparable_for_equality(
                subject_type, case_type
            ):
                token = switch_case.expression().start
                self.errors.report(
                    token.line,
                    token.column,
                    f"el tipo del case '{case_type.name}' no es comparable con el tipo del switch "
                    f"'{subject_type.name}'",
                    "switch-case-tipo-incompatible",
                )
            # Sin 'break' hay fallthrough al siguiente case (decision de equipo:
            # break tambien es valido dentro de un switch, ademas de en bucles).
            self._visit_statements_detecting_dead_code(switch_case.statement())
        if ctx.defaultCase() is not None:
            self._visit_statements_detecting_dead_code(ctx.defaultCase().statement())
        self._switch_depth -= 1
        return None

    def visitVariableDeclaration(self, ctx: CompiscriptParser.VariableDeclarationContext):
        declared_type = self._optional_type(ctx.typeAnnotation())
        symbol = self._predeclared_class_members.get(id(ctx))
        if symbol is None:
            symbol = Symbol(
                name=ctx.Identifier().getText(),
                category=SymbolCategory.VARIABLE,
                type=declared_type,
                initialized=ctx.initializer() is not None,
            )
            self._declare(symbol, ctx)
        if ctx.initializer() is not None:
            value_type = self.visit(ctx.initializer())
            if declared_type is None:
                symbol.type = value_type
            elif value_type is not None and not self._is_assignable(declared_type, value_type):
                token = ctx.initializer().expression().start
                self.errors.report(
                    token.line,
                    token.column,
                    f"no se puede asignar un valor de tipo '{value_type.name}' a la variable "
                    f"'{symbol.name}' de tipo '{declared_type.name}'",
                    "asignacion-tipo-incompatible",
                )
        return None

    def visitConstantDeclaration(self, ctx: CompiscriptParser.ConstantDeclarationContext):
        declared_type = self._optional_type(ctx.typeAnnotation())
        value_type = self.visit(ctx.expression())
        if declared_type is not None and value_type is not None and not self._is_assignable(declared_type, value_type):
            token = ctx.expression().start
            self.errors.report(
                token.line,
                token.column,
                f"no se puede inicializar la constante '{ctx.Identifier().getText()}' de tipo "
                f"'{declared_type.name}' con un valor de tipo '{value_type.name}'",
                "asignacion-tipo-incompatible",
            )
        symbol = self._predeclared_class_members.get(id(ctx))
        if symbol is None:
            symbol = Symbol(
                name=ctx.Identifier().getText(),
                category=SymbolCategory.CONSTANT,
                type=declared_type if declared_type is not None else value_type,
                initialized=True,
            )
            self._declare(symbol, ctx)
        elif symbol.type is None:
            symbol.type = value_type
        return None

    def visitAssignment(self, ctx: CompiscriptParser.AssignmentContext):
        expressions = ctx.expression()
        if len(expressions) == 1:
            name = ctx.Identifier().getText()
            value_type = self.visit(expressions[0])
            symbol = self.symbol_table.resolve(name)
            token = ctx.Identifier().getSymbol()
            if symbol is None:
                self.errors.report(
                    token.line, token.column, f"variable '{name}' no declarada", "uso-variable-no-declarada"
                )
                return None
            self._check_assignment_target(symbol, value_type, token, expressions[0].start)
            return None
        base_type = self.visit(expressions[0])
        value_type = self.visit(expressions[1])
        member = self._resolve_member(base_type, ctx.Identifier())
        if member is not None:
            self._check_assignment_target(
                member, value_type, ctx.Identifier().getSymbol(), expressions[1].start
            )
        return None

    def visitAssignExpr(self, ctx: CompiscriptParser.AssignExprContext):
        value_type = self.visit(ctx.assignmentExpr())
        lhs_type = self.visit(ctx.lhs)
        symbol = getattr(ctx.lhs, "resolved_symbol", None) or self._resolve_simple_identifier(ctx.lhs)
        if symbol is not None:
            token = ctx.lhs.start
            self._check_assignment_target(symbol, value_type, token, ctx.assignmentExpr().start)
        elif lhs_type is not None and value_type is not None and not self._is_assignable(lhs_type, value_type):
            token = ctx.assignmentExpr().start
            self.errors.report(
                token.line,
                token.column,
                f"no se puede asignar un valor de tipo '{value_type.name}' a un valor de tipo '{lhs_type.name}'",
                "asignacion-tipo-incompatible",
            )
        return lhs_type

    def visitPropertyAssignExpr(self, ctx: CompiscriptParser.PropertyAssignExprContext):
        base_type = self.visit(ctx.lhs)
        value_type = self.visit(ctx.assignmentExpr())
        member = self._resolve_member(base_type, ctx.Identifier())
        if member is not None:
            self._check_assignment_target(
                member, value_type, ctx.Identifier().getSymbol(), ctx.assignmentExpr().start
            )
            return member.type
        return None

    def _check_assignment_target(self, symbol: Symbol, value_type: Optional[Type], name_token, value_token) -> None:
        if symbol.category is SymbolCategory.CONSTANT:
            self.errors.report(
                name_token.line,
                name_token.column,
                f"no se puede reasignar la constante '{symbol.name}'",
                "asignacion-a-constante",
            )
            return
        if symbol.type is not None and value_type is not None and not self._is_assignable(symbol.type, value_type):
            self.errors.report(
                value_token.line,
                value_token.column,
                f"no se puede asignar un valor de tipo '{value_type.name}' a '{symbol.name}' "
                f"de tipo '{symbol.type.name}'",
                "asignacion-tipo-incompatible",
            )
            return
        symbol.initialized = True

    def _resolve_simple_identifier(self, left_hand_side_ctx) -> Optional[Symbol]:
        if left_hand_side_ctx.suffixOp():
            return None
        atom = left_hand_side_ctx.primaryAtom()
        if isinstance(atom, CompiscriptParser.IdentifierExprContext):
            return self.symbol_table.resolve(atom.Identifier().getText())
        return None

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        param_ctxs = ctx.parameters().parameter() if ctx.parameters() else []
        param_types = [self._optional_type(param_ctx) for param_ctx in param_ctxs]
        return_type = self._optional_type(ctx)

        function_symbol = self._predeclared_class_members.get(id(ctx))
        if function_symbol is None:
            function_symbol = Symbol(
                name=ctx.Identifier().getText(),
                category=SymbolCategory.FUNCTION,
                type=FunctionType(param_types, return_type),
                initialized=True,
                params=param_types,
                return_type=return_type,
            )
            self._declare(function_symbol, ctx)

        is_method = bool(self._class_stack) and self.symbol_table.current_scope.kind is ScopeKind.CLASS
        self.symbol_table.enter_scope(ScopeKind.FUNCTION)
        self._function_return_stack.append(return_type)
        if is_method:
            self._this_class_stack.append(self._class_stack[-1])
        for param_ctx, param_type in zip(param_ctxs, param_types):
            parameter_symbol = Symbol(
                name=param_ctx.Identifier().getText(),
                category=SymbolCategory.PARAMETER,
                type=param_type,
                initialized=True,
            )
            self._declare(parameter_symbol, param_ctx)
        self._visit_statements_detecting_dead_code(ctx.block().statement())
        if is_method:
            self._this_class_stack.pop()
        self._function_return_stack.pop()
        self.symbol_table.exit_scope()

        if return_type is not None and not self._block_always_returns(ctx.block()):
            token = ctx.block().start
            self.errors.report(
                token.line,
                token.column,
                f"la funcion '{function_symbol.name}' declara tipo de retorno '{return_type.name}' "
                f"pero no garantiza un 'return' en todos los caminos",
                "return-faltante-en-algun-camino",
            )
        return None

    def _block_always_returns(self, block_ctx: CompiscriptParser.BlockContext) -> bool:
        return any(self._statement_always_returns(statement) for statement in block_ctx.statement())

    def _statement_always_returns(self, ctx: CompiscriptParser.StatementContext) -> bool:
        if ctx.returnStatement() is not None:
            return True
        if ctx.ifStatement() is not None:
            blocks = ctx.ifStatement().block()
            if len(blocks) < 2:
                return False
            return all(self._block_always_returns(block) for block in blocks)
        if ctx.doWhileStatement() is not None:
            return self._block_always_returns(ctx.doWhileStatement().block())
        if ctx.block() is not None:
            return self._block_always_returns(ctx.block())
        return False

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

        if parent_class is not None:
            parent_symbol = self.symbol_table.resolve_class(parent_class)
            token = identifiers[1].getSymbol()
            if parent_symbol is None:
                self.errors.report(
                    token.line,
                    token.column,
                    f"la clase base '{parent_class}' no esta declarada",
                    "clase-base-no-declarada",
                )
            elif parent_symbol is class_symbol or self._inherits_from(parent_symbol, name):
                self.errors.report(
                    token.line,
                    token.column,
                    f"la herencia de la clase '{name}' forma un ciclo",
                    "herencia-ciclica",
                )

        class_symbol.class_scope = self.symbol_table.enter_scope(ScopeKind.CLASS)
        self._class_stack.append(class_symbol)
        for member in ctx.classMember():
            self._predeclare_class_member(member)
        for member in ctx.classMember():
            self.visit(member)
        self._class_stack.pop()
        self.symbol_table.exit_scope()
        return None

    def _predeclare_class_member(self, member_ctx) -> None:
        declaration = member_ctx.getChild(0)
        if isinstance(declaration, CompiscriptParser.FunctionDeclarationContext):
            param_ctxs = declaration.parameters().parameter() if declaration.parameters() else []
            param_types = [self._optional_type(param_ctx) for param_ctx in param_ctxs]
            return_type = self._optional_type(declaration)
            symbol = Symbol(
                name=declaration.Identifier().getText(),
                category=SymbolCategory.FUNCTION,
                type=FunctionType(param_types, return_type),
                initialized=True,
                params=param_types,
                return_type=return_type,
            )
        else:
            declared_type = self._optional_type(declaration.typeAnnotation())
            is_constant = isinstance(declaration, CompiscriptParser.ConstantDeclarationContext)
            symbol = Symbol(
                name=declaration.Identifier().getText(),
                category=SymbolCategory.CONSTANT if is_constant else SymbolCategory.VARIABLE,
                type=declared_type,
                initialized=is_constant or declaration.initializer() is not None,
            )
        self._predeclared_class_members[id(declaration)] = symbol
        self._declare(symbol, declaration)

    def _inherits_from(self, class_symbol: Symbol, target_name: str) -> bool:
        visited = set()
        while class_symbol is not None and class_symbol.name not in visited:
            if class_symbol.name == target_name:
                return True
            visited.add(class_symbol.name)
            if class_symbol.parent_class is None:
                return False
            class_symbol = self.symbol_table.resolve_class(
                class_symbol.parent_class, class_symbol.scope
            )
        return False

    def visitThisExpr(self, ctx: CompiscriptParser.ThisExprContext):
        if not self._this_class_stack:
            token = ctx.start
            self.errors.report(
                token.line,
                token.column,
                "'this' solo es valido dentro de un metodo de clase",
                "this-fuera-de-metodo",
            )
            return None
        return self._this_class_stack[-1].type

    def visitNewExpr(self, ctx: CompiscriptParser.NewExprContext):
        name = ctx.Identifier().getText()
        class_symbol = self.symbol_table.resolve_class(name)
        argument_ctxs = ctx.arguments().expression() if ctx.arguments() is not None else []
        argument_types = [self.visit(argument) for argument in argument_ctxs]
        if class_symbol is None:
            token = ctx.Identifier().getSymbol()
            self.errors.report(
                token.line,
                token.column,
                f"no se puede construir la clase no declarada '{name}'",
                "new-clase-no-declarada",
            )
            return None

        constructor = (
            class_symbol.class_scope.resolve_local("constructor")
            if class_symbol.class_scope is not None
            else None
        )
        if constructor is None:
            if argument_ctxs:
                token = ctx.start
                self.errors.report(
                    token.line,
                    token.column,
                    f"la clase '{name}' no declara constructor y solo admite cero argumentos",
                    "constructor-numero-argumentos-invalido",
                )
        elif not isinstance(constructor.type, FunctionType):
            token = ctx.start
            self.errors.report(
                token.line,
                token.column,
                f"el miembro 'constructor' de '{name}' no es una funcion",
                "constructor-no-funcion",
            )
        else:
            self._check_call_arguments(constructor.type, argument_ctxs, argument_types, ctx)
        return class_symbol.type

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
            if previous_type is not None and current_type is not None and not self._comparable_for_equality(
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
        resolved_symbol = None
        for suffix in ctx.suffixOp():
            if isinstance(suffix, CompiscriptParser.PropertyAccessExprContext):
                resolved_symbol = self._resolve_member(current_type, suffix.Identifier())
                current_type = resolved_symbol.type if resolved_symbol is not None else None
            else:
                current_type = self._apply_suffix(current_type, suffix)
                resolved_symbol = None
        ctx.resolved_symbol = resolved_symbol
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
            argument_ctxs = suffix_ctx.arguments().expression() if suffix_ctx.arguments() is not None else []
            argument_types = [self.visit(argument_ctx) for argument_ctx in argument_ctxs]
            if base_type is None:
                return None
            if not isinstance(base_type, FunctionType):
                token = suffix_ctx.start
                self.errors.report(
                    token.line,
                    token.column,
                    f"no se puede invocar un valor de tipo '{base_type.name}'",
                    "llamada-sobre-no-funcion",
                )
                return None
            self._check_call_arguments(base_type, argument_ctxs, argument_types, suffix_ctx)
            return base_type.return_type
        return None

    def _resolve_member(self, base_type: Optional[Type], identifier) -> Optional[Symbol]:
        if base_type is None:
            return None
        token = identifier.getSymbol()
        member_name = identifier.getText()
        if not isinstance(base_type, ClassType):
            self.errors.report(
                token.line,
                token.column,
                f"no se puede acceder al miembro '{member_name}' sobre un valor de tipo '{base_type.name}'",
                "acceso-miembro-sobre-no-objeto",
            )
            return None
        class_symbol = self.symbol_table.resolve_class(base_type.class_name)
        if class_symbol is None:
            self.errors.report(
                token.line,
                token.column,
                f"el tipo de clase '{base_type.class_name}' no esta declarado",
                "tipo-clase-no-declarada",
            )
            return None
        member = self.symbol_table.resolve_member(base_type.class_name, member_name)
        if member is None:
            self.errors.report(
                token.line,
                token.column,
                f"la clase '{base_type.class_name}' no tiene un miembro llamado '{member_name}'",
                "miembro-no-existente",
            )
        return member

    def _check_call_arguments(self, function_type: FunctionType, argument_ctxs, argument_types, ctx) -> None:
        expected_types = function_type.params
        if len(argument_types) != len(expected_types):
            token = ctx.start
            self.errors.report(
                token.line,
                token.column,
                f"se esperaban {len(expected_types)} argumento(s) y se recibieron {len(argument_types)}",
                "llamada-numero-argumentos-invalido",
            )
            return
        for argument_ctx, argument_type, expected_type in zip(argument_ctxs, argument_types, expected_types):
            if expected_type is not None and argument_type is not None and not self._is_assignable(
                expected_type, argument_type
            ):
                token = argument_ctx.start
                self.errors.report(
                    token.line,
                    token.column,
                    f"el argumento de tipo '{argument_type.name}' no es compatible con el parametro "
                    f"de tipo '{expected_type.name}'",
                    "llamada-tipo-argumento-invalido",
                )

    def _is_assignable(self, target: Optional[Type], value: Optional[Type]) -> bool:
        if is_assignable(target, value):
            return True
        if isinstance(target, ClassType) and isinstance(value, ClassType):
            value_class = self.symbol_table.resolve_class(value.class_name)
            return value_class is not None and self._inherits_from(value_class, target.class_name)
        return False

    def _comparable_for_equality(self, left: Optional[Type], right: Optional[Type]) -> bool:
        return (
            comparable_for_equality(left, right)
            or self._is_assignable(left, right)
            or self._is_assignable(right, left)
        )

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
