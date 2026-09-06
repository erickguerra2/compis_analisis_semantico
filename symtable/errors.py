class DuplicateSymbolError(Exception):
    def __init__(self, name: str):
        super().__init__(f"'{name}' ya esta declarado en este ambito")
        self.name = name
