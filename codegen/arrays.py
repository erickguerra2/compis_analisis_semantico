from __future__ import annotations

from tac import Const, Temp

OUT_OF_RANGE = "indice fuera de rango"


class ArraysMixin:
    def gen_array_literal(self, ctx):
        elements = ctx.expression()
        array = self.emitter.new_temp()
        self.emitter.emit("new_array", Const(len(elements)), res=array)
        for position, element_ctx in enumerate(elements):
            value = self.visit(element_ctx)
            self.emitter.emit("index_store", Const(position), value, array)
            self.emitter.free_temp(value)
        return array

    def gen_index(self, base, index_ctx, ctx):
        index = self.visit(index_ctx)
        self._check_bounds(base, index)
        self.emitter.free_temp(base)
        self.emitter.free_temp(index)
        result = self.emitter.new_temp()
        self.emitter.emit("index_load", base, index, result)
        return result

    def gen_index_store(self, base, index_ctx, value, ctx):
        index = self.visit(index_ctx)
        self._check_bounds(base, index)
        self.emitter.emit("index_store", index, value, base)
        self.emitter.free_temp(base)
        self.emitter.free_temp(index)
        return value

    def visitForeachStatement(self, ctx):
        iterable = self.visit(ctx.expression())
        array = iterable
        if not isinstance(iterable, Temp):
            # Se copia para que reasignar la variable dentro del cuerpo no cambie el recorrido.
            array = self.emitter.new_temp()
            self.emitter.emit("copy", iterable, res=array)
        length = self.emitter.new_temp()
        self.emitter.emit("len", array, res=length)
        position = self.emitter.new_temp()
        self.emitter.emit("copy", Const(0), res=position)
        start = self.emitter.new_label()
        again = self.emitter.new_label()
        end = self.emitter.new_label()
        self.emitter.place_label(start)
        condition = self.emitter.new_temp()
        self.emitter.emit("<", position, length, condition)
        self.emitter.emit("ifFalse", condition, res=end)
        self.emitter.free_temp(condition)
        self.emitter.emit("index_load", array, position, self._declare_var(ctx))
        self._loop_body(ctx.block(), end, again)
        self.emitter.place_label(again)
        self.emitter.emit("+", position, Const(1), position)
        self.emitter.emit("goto", res=start)
        self.emitter.place_label(end)
        for temp in (array, length, position):
            self.emitter.free_temp(temp)
        return None

    def _check_bounds(self, base, index):
        # `bounds` lanza este mensaje si el índice se sale del arreglo (4.6.7).
        self.emitter.intern_string(OUT_OF_RANGE)
        self.emitter.emit("bounds", base, index)
