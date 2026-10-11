from tac import Const


class FunctionsMixin:
    def visitFunctionDeclaration(self, ctx):
        self.pending.append(ctx)

    def _emit_function(self, ctx):
        symbol = self._symbol_of(ctx)
        self.loop_stack = []
        self.try_depth = 0
        self.emitter.begin_function(symbol.label)
        for statement in ctx.block().statement():
            self.visit(statement)
        if self.emitter.quads[-1].op != "return":
            self.emitter.emit("return")
        self.emitter.end_function(symbol.label)

    def gen_function_call(self, symbol, args_ctx, ctx):
        arguments = [self.visit(arg) for arg in args_ctx.expression()] if args_ctx else []
        for operand in arguments:
            self.emitter.emit("param", operand)
        for operand in arguments:
            self.emitter.free_temp(operand)
        result = self.emitter.new_temp() if symbol.return_type is not None else None
        self.emitter.emit("call", symbol.label, Const(len(arguments)), result)
        return result

    def visitReturnStatement(self, ctx):
        value = self.visit(ctx.expression()) if ctx.expression() else None
        for _ in range(self.try_depth):
            self.emitter.emit("try_end")
        self.emitter.emit("return", value)
        self.emitter.free_temp(value)
