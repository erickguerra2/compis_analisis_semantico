from __future__ import annotations


class ControlFlowMixin:
    def visitIfStatement(self, ctx):
        blocks = ctx.block()
        otherwise = self.emitter.new_label()
        self._jump_if_false(ctx.expression(), otherwise)
        self.visit(blocks[0])
        if len(blocks) == 1:
            self.emitter.place_label(otherwise)
            return None
        end = self.emitter.new_label()
        self.emitter.emit("goto", res=end)
        self.emitter.place_label(otherwise)
        self.visit(blocks[1])
        self.emitter.place_label(end)
        return None

    def visitWhileStatement(self, ctx):
        start = self.emitter.new_label()
        end = self.emitter.new_label()
        self.emitter.place_label(start)
        self._jump_if_false(ctx.expression(), end)
        self._loop_body(ctx.block(), end, start)
        self.emitter.emit("goto", res=start)
        self.emitter.place_label(end)
        return None

    def visitDoWhileStatement(self, ctx):
        start = self.emitter.new_label()
        again = self.emitter.new_label()
        end = self.emitter.new_label()
        self.emitter.place_label(start)
        self._loop_body(ctx.block(), end, again)
        self.emitter.place_label(again)
        condition = self.visit(ctx.expression())
        self.emitter.emit("if", condition, res=start)
        self.emitter.free_temp(condition)
        self.emitter.place_label(end)
        return None

    def visitForStatement(self, ctx):
        if ctx.variableDeclaration() is not None:
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment() is not None:
            self.visit(ctx.assignment())
        condition_ctx, update_ctx = self._for_header(ctx)
        start = self.emitter.new_label()
        again = self.emitter.new_label()
        end = self.emitter.new_label()
        self.emitter.place_label(start)
        if condition_ctx is not None:
            self._jump_if_false(condition_ctx, end)
        self._loop_body(ctx.block(), end, again)
        self.emitter.place_label(again)
        if update_ctx is not None:
            self.emitter.free_temp(self.visit(update_ctx))
        self.emitter.emit("goto", res=start)
        self.emitter.place_label(end)
        return None

    def visitSwitchStatement(self, ctx):
        cases = ctx.switchCase()
        default_ctx = ctx.defaultCase()
        subject = self.visit(ctx.expression())
        case_labels = [self.emitter.new_label() for _ in cases]
        default_label = self.emitter.new_label() if default_ctx is not None else None
        end = self.emitter.new_label()
        for case_ctx, label in zip(cases, case_labels):
            value = self.visit(case_ctx.expression())
            self.emitter.free_temp(value)
            matches = self.emitter.new_temp()
            self.emitter.emit("==", subject, value, matches)
            self.emitter.emit("if", matches, res=label)
            self.emitter.free_temp(matches)
        self.emitter.emit("goto", res=default_label or end)
        self.emitter.free_temp(subject)
        self.loop_stack.append((end, None, self.try_depth))
        for case_ctx, label in zip(cases, case_labels):
            self.emitter.place_label(label)
            for statement in case_ctx.statement():
                self.visit(statement)
        if default_ctx is not None:
            self.emitter.place_label(default_label)
            for statement in default_ctx.statement():
                self.visit(statement)
        self.loop_stack.pop()
        self.emitter.place_label(end)
        return None

    def visitTryCatchStatement(self, ctx):
        try_block, catch_block = ctx.block()
        handler = self.emitter.new_label()
        end = self.emitter.new_label()
        self.emitter.emit("try_begin", handler)
        self.try_depth += 1
        self.visit(try_block)
        self.try_depth -= 1
        self.emitter.emit("try_end")
        self.emitter.emit("goto", res=end)
        self.emitter.place_label(handler)
        self.emitter.emit("catch", self._declare_var(ctx))
        self.visit(catch_block)
        self.emitter.place_label(end)
        return None

    def visitBreakStatement(self, ctx):
        break_label, _, try_depth = self.loop_stack[-1]
        self._leave_tries(try_depth)
        self.emitter.emit("goto", res=break_label)
        return None

    def visitContinueStatement(self, ctx):
        _, continue_label, try_depth = next(entry for entry in reversed(self.loop_stack) if entry[1] is not None)
        self._leave_tries(try_depth)
        self.emitter.emit("goto", res=continue_label)
        return None

    def _jump_if_false(self, condition_ctx, target):
        condition = self.visit(condition_ctx)
        self.emitter.emit("ifFalse", condition, res=target)
        self.emitter.free_temp(condition)

    def _loop_body(self, block_ctx, break_label, continue_label):
        self.loop_stack.append((break_label, continue_label, self.try_depth))
        self.visit(block_ctx)
        self.loop_stack.pop()

    def _leave_tries(self, try_depth):
        for _ in range(self.try_depth - try_depth):
            self.emitter.emit("try_end")

    def _for_header(self, ctx):
        middle = next(index for index in range(3, ctx.getChildCount()) if ctx.getChild(index).getText() == ";")
        condition_ctx = ctx.getChild(3) if middle != 3 else None
        update_ctx = ctx.getChild(middle + 1) if ctx.getChild(middle + 1).getText() != ")" else None
        return condition_ctx, update_ctx
