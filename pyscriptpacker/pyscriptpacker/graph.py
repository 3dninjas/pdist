import os
import sys
import ast

from toposort import toposort_flatten


class ImportInfo(object):
    """
    A record of a name and the location of the import statement.
    """

    def __init__(self, name, level):
        self.name = name
        self.level = level

    def __repr__(self):
        # Used for debugging (print to console)
        return '%s(%r, %r)' % (
            self.__class__.__name__,
            self.name,
            self.level,
        )


class ImportFinder(ast.NodeVisitor):
    """
    This class is implemented as a NodeVisitor which will collect all the
    import dependencies when visit a new file as root.

    Reference: https://www.mattlayman.com/blog/2018/decipher-python-ast/
    """

    def __init__(self, file_name, file_path):
        self._imports = []

        with open(os.path.join(file_path, file_name)) as f:
            root = ast.parse(f.read(), file_name)
        self.visit(root)

    @property
    def list_imports(self):
        return self._imports

    def visit_Import(self, node):
        for alias in node.names:
            self._process(alias.name, None)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            fullname = '%s.%s' % (node.module,
                                  alias.name) if node.module else alias.name
            self._process(fullname, node.level)

    def _process(self, full_name, level):
        info = ImportInfo(full_name, level)
        self._imports.append(info)


class Module(object):
    """
    Node in a module dependency graph.
    """

    def __init__(self, module_name, file_name):
        self.module_name = module_name
        self.file_name = file_name
        self.is_package = False
        self.content = ''
        self.imports = set()

    def to_dict(self):
        data = {
            'name': self.module_name,
            'is_package': self.is_package,
            'code': self.content,
        }
        return data

    def __repr__(self):
        # Used for debugging (print to console)
        return '<%s: %s>:\nFile: %r\nPackage: %r\nCode: %r\nImport: %r\n' % (
            self.__class__.__name__,
            self.module_name,
            self.file_name,
            self.is_package,
            self.content,
            self.imports,
        )


class ModuleGraph(object):
    """
    Module graph tree used for detect import dependencies and order them
    if necessary.
    """

    def __init__(self):
        self._modules = {}
        self._module_cache = {}
        self._paths = list(sys.path)

    def generate_data(self):
        data = []

        list_dependencies = self._build_dependency_data()
        for module in list_dependencies:
            data.append(self._modules[module].to_dict())

        return data

    def parse_paths(self, paths):
        for path in paths:
            if not os.path.exists(path):
                return

            for root, _, files in os.walk(path):
                self._paths.append(root)

                for file in files:
                    # TODO(Nghia Lam): I exclude `setup.py` because some
                    # structure does put the `setup.py` outside of the module
                    # folder, not inside it. Do we have a better way to solve
                    # this?
                    if file.endswith('.py') and file != 'setup.py':
                        self.parse_file(file, root)

    def parse_file(self, file_name, file_path):
        # NOTE(Nghia Lam): We did make sure the default file_path contain at
        # least one python file, it means that the main folder in file_path is
        # a module. But we need to make get all the parent scope of the module
        # to avoid name clashes.
        module_name = self._find_module_name(file_name, file_path)
        module = Module(module_name, file_name)
        module.is_package = (file_name == '__init__.py')
        # Read code content
        with open(os.path.join(file_path, file_name), 'r') as file_data:
            module.content = file_data.read()
        # Get import dependencies
        import_infos = ImportFinder(file_name, file_path).list_imports
        module.imports = {
            self._find_module_of_import(imp.name, imp.level, file_path)
            for imp in import_infos
        }
        # NOTE(Nghia Lam): Remove standard python libraries (which has returned
        # None when finding module.)
        module.imports = {imp for imp in module.imports if imp is not None}

        self._modules[module_name] = module

    def _find_module_name(self, file_name, file_path):
        module_name = []

        elements = file_path.split(os.path.sep)
        while elements:
            module_name.append(elements.pop())
            # Stop when there's any python file
            contain_python = any(
                '.py' in file and file != 'setup.py'
                for file in os.listdir(os.path.sep.join(elements)))
            if not contain_python:
                break
        module_name.reverse()
        module_name = '.'.join(module_name)

        # Add file name to module name for scope management
        if '__init__.py' not in file_name:
            file_name = file_name.split('.py')[0]
            # Remove trailing namespace
            if os.path.sep in file_name:
                file_name = file_name.split(os.path.sep)[-1]
            module_name += '.' + file_name

        return module_name

    def _find_module_of_import(self, imp_name, imp_level, file_path):
        """Given a fully qualified name, find what module contains it."""
        if imp_name in sys.modules or imp_name in sys.builtin_module_names:
            return None
        if imp_name.endswith('.*'):
            return imp_name[:-2]

        name = imp_name

        extrapath = None
        if imp_level and imp_level > 1:
            # NOTE(Nghia Lam): Find the trailling path if the level is > 1 for
            # relative import.
            # from .. import something
            # --> The path must go up one
            # from ... import something
            # --> The path must go up two
            extrapath = file_path.split(os.path.sep)
            imp_level -= 1
            extrapath = extrapath[0:-imp_level]
            extrapath = os.path.sep.join(extrapath)

        if (imp_name, extrapath) in self._module_cache:
            return self._module_cache[(imp_name, extrapath)]

        while name:
            result = self._get_name_via_module(name, extrapath)
            if result:
                return result
            result = self._get_name_via_package(name, extrapath)
            if result:
                return result

            name = name.rpartition('.')[0]

        return imp_name

    def _get_name_via_module(self, imp_name, extrapath=None):
        imp_filename = imp_name.replace('.', os.path.sep) + '.py'

        if extrapath:
            full_path = os.path.join(extrapath, imp_filename)
            if os.path.exists(full_path):
                module_name = self._find_module_name(imp_filename,
                                                     os.path.dirname(full_path))
                self._module_cache[(imp_name, extrapath)] = module_name
                return module_name

        for path in self._paths:
            if not os.path.isfile(path):
                full_path = os.path.join(path, imp_filename)
                if os.path.exists(full_path):
                    module_name = self._find_module_name(
                        imp_filename, os.path.dirname(full_path))
                    self._module_cache[(imp_name, extrapath)] = module_name
                    return module_name

        return None

    def _get_name_via_package(self, imp_name, extrapath=None):
        return self._get_name_via_module(imp_name + '.__init__', extrapath)

    def _build_dependency_data(self):
        data = {}
        for key in self._modules:
            data[key] = self._modules[key].imports

        return toposort_flatten(data)