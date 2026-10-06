from __future__ import annotations

from generated.CompiscriptParser import CompiscriptParser

from semantic.types import BOOLEAN, INTEGER, STRING
from tac.quad import Const, Temp, Var


class ExpressionsMixin:
    def visitVariableDeclaration(self, ctx):
        target = self._declare_var(ctx)
        value = self.visit(ctx.initializer().expression()) if ctx.initializer() is not None else self._default_value(ctx)
        self.emitter.emit("copy", value, res=target)
        self.emitter.free_temp(value)
        return target

    def visitConstantDeclaration(self, ctx):
        target = self._declare_var(ctx)
        value = self.visit(ctx.expression())
        self.emitter.emit("copy", value, res=target)
        self.emitter.free_temp(value)
        return target

    def visitAssignment(self, ctx):
        expressions = ctx.expression()
        if len(expressions) != 1:
            raise NotImplementedError("construcción no soportada todavía")
        symbol = self._resolve_name(ctx.Identifier().getText(), ctx)
        target = self._var_for_symbol(symbol)
        value = self.visit(expressions[0])
        self.emitter.emit("copy", value, res=target)
        self.emitter.free_temp(value)
        return target

    def visitExpressionStatement(self, ctx):
        value = self.visit(ctx.expression())
        self.emitter.free_temp(value)
        return None

    def visitPrintStatement(self, ctx):
        value = self.visit(ctx.expression())
        self.emitter.emit("print", value)
        self.emitter.free_temp(value)
        return None

    def visitAssignExpr(self, ctx):
        value = self.visit(ctx.assignmentExpr())
        lhs = ctx.lhs
        if lhs.suffixOp():
            raise NotImplementedError("construcción no soportada todavía")
        symbol = self._symbol_of(lhs) or self._symbol_of(lhs.primaryAtom())
        target = self._var_for_symbol(symbol)
        self.emitter.emit("copy", value, res=target)
        self.emitter.free_temp(value)
        return target

    def visitPropertyAssignExpr(self, ctx):
        raise NotImplementedError("construcción no soportada todavía")

    def visitExprNoAssign(self, ctx):
        return self.visit(ctx.conditionalExpr())

    def visitTernaryExpr(self, ctx):
        branches = ctx.expression()
        if not branches:
            return self.visit(ctx.logicalOrExpr())
        result = self.emitter.new_temp()
        otherwise = self.emitter.new_label()
        end = self.emitter.new_label()
        condition = self.visit(ctx.logicalOrExpr())
        self.emitter.emit("ifFalse", condition, res=otherwise)
        self.emitter.free_temp(condition)
        yes = self.visit(branches[0])
        self.emitter.emit("copy", yes, res=result)
        self.emitter.free_temp(yes)
        self.emitter.emit("goto", res=end)
        self.emitter.place_label(otherwise)
        no = self.visit(branches[1])
        self.emitter.emit("copy", no, res=result)
        self.emitter.free_temp(no)
        self.emitter.place_label(end)
        return result

    def visitLogicalOrExpr(self, ctx):
        return self._short_circuit(ctx.logicalAndExpr(), "if")

    def visitLogicalAndExpr(self, ctx):
        return self._short_circuit(ctx.equalityExpr(), "ifFalse")

    def _short_circuit(self, operands, jump):
        if len(operands) == 1:
            return self.visit(operands[0])
        result = self.emitter.new_temp()
        end = self.emitter.new_label()
        for index, operand_ctx in enumerate(operands):
            operand = self.visit(operand_ctx)
            self.emitter.emit("copy", operand, res=result)
            self.emitter.free_temp(operand)
            if index != len(operands) - 1:
                self.emitter.emit(jump, result, res=end)
        self.emitter.place_label(end)
        return result

    def visitEqualityExpr(self, ctx):
        return self._binary_chain(ctx, ctx.relationalExpr())

    def visitRelationalExpr(self, ctx):
        return self._binary_chain(ctx, ctx.additiveExpr())

    def visitAdditiveExpr(self, ctx):
        operands = ctx.multiplicativeExpr()
        value = self.visit(operands[0])
        value_type = self._type_of(operands[0])
        for index in range(1, len(operands)):
            right_ctx = operands[index]
            right = self.visit(right_ctx)
            right_type = self._type_of(right_ctx)
            operator = ctx.getChild(2 * index - 1).getText()
            if operator == "+" and (value_type == STRING or right_type == STRING):
                value = self._as_string(value, value_type)
                right = self._as_string(right, right_type)
                result = self._consume_binary("concat", value, right)
                value_type = STRING
            else:
                result = self._consume_binary(operator, value, right)
                value_type = self._type_of(ctx) if index == len(operands) - 1 else value_type
            value = result
        return value

    def visitMultiplicativeExpr(self, ctx):
        return self._binary_chain(ctx, ctx.unaryExpr())

    def _binary_chain(self, ctx, operands):
        value = self.visit(operands[0])
        for index in range(1, len(operands)):
            right = self.visit(operands[index])
            value = self._consume_binary(ctx.getChild(2 * index - 1).getText(), value, right)
        return value

    def _consume_binary(self, op, left, right):
        self.emitter.free_temp(left)
        self.emitter.free_temp(right)
        result = self.emitter.new_temp()
        self.emitter.emit(op, left, right, result)
        return result

    def _as_string(self, operand, type_):
        if type_ == STRING:
            return operand
        self.emitter.free_temp(operand)
        result = self.emitter.new_temp()
        self.emitter.emit("to_str", operand, res=result)
        return result

    def visitUnaryExpr(self, ctx):
        if ctx.unaryExpr() is None:
            return self.visit(ctx.primaryExpr())
        operand = self.visit(ctx.unaryExpr())
        self.emitter.free_temp(operand)
        result = self.emitter.new_temp()
        self.emitter.emit("neg" if ctx.getChild(0).getText() == "-" else "not", operand, res=result)
        return result

    def visitPrimaryExpr(self, ctx):
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        return self.visit(ctx.expression())

    def visitLiteralExpr(self, ctx):
        if ctx.arrayLiteral() is not None:
            return self.gen_array_literal(ctx.arrayLiteral())
        text = ctx.getText()
        if text == "true":
            return Const(True)
        if text == "false":
            return Const(False)
        if text == "null":
            return Const(None)
        if text.startswith('"'):
            return self.emitter.intern_string(text[1:-1])
        return Const(int(text))

    def visitLeftHandSide(self, ctx):
        atom = ctx.primaryAtom()
        if isinstance(atom, CompiscriptParser.IdentifierExprContext):
            symbol = self._symbol_of(atom) or self._symbol_of(ctx)
            value = self._var_for_symbol(symbol)
        elif isinstance(atom, CompiscriptParser.NewExprContext):
            value = self.gen_new(self._symbol_of(atom), atom.arguments(), atom)
        elif isinstance(atom, CompiscriptParser.ThisExprContext):
            value = self.gen_this(atom)
        else:
            raise NotImplementedError("construcción no soportada todavía")
        for suffix in ctx.suffixOp():
            if isinstance(suffix, CompiscriptParser.CallExprContext):
                value = self.gen_function_call(symbol, suffix.arguments(), suffix)
            elif isinstance(suffix, CompiscriptParser.IndexExprContext):
                value = self.gen_index(value, suffix.expression(), suffix)
            else:
                value = self.gen_property(value, suffix.Identifier().getText(), suffix)
        return value

    def _default_value(self, ctx):
        type_ = self._type_of(ctx)
        if type_ == INTEGER:
            return Const(0)
        if type_ == BOOLEAN:
            return Const(False)
        return Const(None)
