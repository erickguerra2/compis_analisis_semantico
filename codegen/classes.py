from __future__ import annotations

from tac import Const, Var


class ClassesMixin:
    def visitClassDeclaration(self, ctx):
        # La clase no emite código en su sitio: sus métodos se emiten después de main.
        self.class_declarations[id(self._symbol_of(ctx))] = ctx
        for member in ctx.classMember():
            if member.functionDeclaration() is not None:
                self.pending.append(member.functionDeclaration())
        return None

    def gen_new(self, class_symbol, args_ctx, ctx):
        if class_symbol is None:
            class_symbol = self._annotation(ctx).scope.resolve(ctx.Identifier().getText())
        instance = self.emitter.new_temp()
        self.emitter.emit("new", class_symbol.name, res=instance)
        chain = self._class_chain(class_symbol)
        for owner in reversed(chain):
            self._emit_field_initializers(owner, instance)
        constructors = (owner.class_scope.resolve_local("constructor") for owner in chain)
        constructor = next((symbol for symbol in constructors if symbol is not None), None)
        if constructor is not None:
            self._call_with_receiver(constructor, instance, args_ctx, release_receiver=False)
        return instance

    def gen_method_call(self, receiver, method_symbol, args_ctx, ctx):
        return self._call_with_receiver(method_symbol, receiver, args_ctx, release_receiver=True)

    def gen_this(self, ctx):
        return Var("this")

    def gen_property(self, base, name, ctx):
        self.emitter.free_temp(base)
        result = self.emitter.new_temp()
        self.emitter.emit("field_load", base, name, result)
        return result

    def gen_property_store(self, base, name, value, ctx):
        self.emitter.emit("field_store", name, value, base)
        self.emitter.free_temp(base)
        return value

    def _call_with_receiver(self, method_symbol, receiver, args_ctx, release_receiver):
        arguments = [self.visit(arg) for arg in args_ctx.expression()] if args_ctx else []
        for operand in [receiver] + arguments:
            self.emitter.emit("param", operand)
        for operand in arguments:
            self.emitter.free_temp(operand)
        if release_receiver:
            self.emitter.free_temp(receiver)
        result = self.emitter.new_temp() if method_symbol.return_type is not None else None
        self.emitter.emit("call", method_symbol.label, Const(len(arguments) + 1), result)
        return result

    def _class_chain(self, class_symbol):
        """La clase y sus ancestros, de la más derivada a la raíz."""
        chain = []
        while class_symbol is not None and all(known is not class_symbol for known in chain):
            chain.append(class_symbol)
            if class_symbol.parent_class is None:
                break
            class_symbol = self.analyzer.symbol_table.resolve_class(class_symbol.parent_class, class_symbol.scope)
        return chain

    def _emit_field_initializers(self, class_symbol, instance):
        for member in self.class_declarations[id(class_symbol)].classMember():
            if member.variableDeclaration() is not None:
                declaration = member.variableDeclaration()
                initializer = declaration.initializer()
                value_ctx = initializer.expression() if initializer is not None else None
            elif member.constantDeclaration() is not None:
                declaration = member.constantDeclaration()
                value_ctx = declaration.expression()
            else:
                continue
            if value_ctx is None:
                continue
            value = self.visit(value_ctx)
            self.emitter.emit("field_store", declaration.Identifier().getText(), value, instance)
            self.emitter.free_temp(value)
