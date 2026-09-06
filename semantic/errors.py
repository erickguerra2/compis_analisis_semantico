from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class SemanticError:
    line: int
    column: int
    message: str
    rule: str


class ErrorReporter:
    def __init__(self):
        self.errors: List[SemanticError] = []

    def report(self, line: int, column: int, message: str, rule: str) -> None:
        self.errors.append(SemanticError(line, column, message, rule))

    def has_errors(self) -> bool:
        return len(self.errors) > 0
