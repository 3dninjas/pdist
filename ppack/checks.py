import ast


class _HasAbsoluteImportOfModuleCheck(ast.NodeTransformer):

    def __init__(self, module):
        self._module = module
        self.has_absolute_import_of_module = False
        super().__init__()

    def visit_Import(self, node: ast.Import):
        for name in node.names:
            if name.name == self._module or name.name.startswith(self._module + '.'):
                self.has_absolute_import_of_module = True
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.level == 0:
            if node.module == self._module or node.module.startswith(self._module + '.'):
                self.has_absolute_import_of_module = True
        return node


def has_absolute_import_of_module(source, module):
    visitor = _HasAbsoluteImportOfModuleCheck(module)
    visitor.visit(ast.parse(source, type_comments=True))
    return visitor.has_absolute_import_of_module


class _HasRelativeImportCheck(ast.NodeTransformer):

    def __init__(self):
        self.has_relative_import = False
        super().__init__()

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.level != 0:
            self.has_relative_import = True
        return node


def has_relative_import(source):
    visitor = _HasRelativeImportCheck()
    visitor.visit(ast.parse(source, type_comments=True))
    return visitor.has_relative_import