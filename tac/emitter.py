from __future__ import annotations

import json

from .quad import Label, Quad, StrLit, Temp
from .temps import TempPool


class Emitter:
    def __init__(self) -> None:
        self.quads: list[Quad] = []
        self.strings: dict[str, str] = {}
        self.function_temps: dict[str, int] = {}
        self._string_labels: dict[str, StrLit] = {}
        self._labels = 0
        self._temps = TempPool()
        self._function: str | None = None

    def emit(self, op, a1=None, a2=None, res=None) -> Quad:
        quad = Quad(op, a1, a2, res)
        self.quads.append(quad)
        return quad

    def new_temp(self) -> Temp:
        return self._temps.acquire()

    def free_temp(self, operand) -> None:
        if isinstance(operand, Temp):
            self._temps.release(operand)

    def new_label(self) -> Label:
        label = Label(f"L{self._labels}")
        self._labels += 1
        return label

    def place_label(self, label: Label) -> None:
        self.emit("label", res=label)

    def intern_string(self, text: str) -> StrLit:
        if text not in self._string_labels:
            literal = StrLit(f".str{len(self.strings)}")
            self._string_labels[text] = literal
            self.strings[literal.label] = text
        return self._string_labels[text]

    def live_temps(self) -> int:
        return self._temps.live()

    def begin_function(self, name: str) -> None:
        self._function = name
        self._temps.reset()
        self.emit("begin_func", name)

    def end_function(self, name: str) -> None:
        self.emit("end_func", name)
        self.function_temps[name] = self._temps.maximum
        self._function = None

    def lines(self) -> list[str]:
        return [str(quad) for quad in self.quads]

    def dump(self) -> str:
        body = "\n".join(f"    {line}" for line in self.lines())
        if not self.strings:
            return body
        data = [".data"] + [f"    {label}: {json.dumps(text, ensure_ascii=False)}" for label, text in self.strings.items()]
        return "\n".join(data + [".code", body])
