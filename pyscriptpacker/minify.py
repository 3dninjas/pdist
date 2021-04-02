import os

from pyminifier import minification
from pyminifier import token_utils
from pyminifier import obfuscate


class MinifyConfig(object):
    '''
    Configuration for the wrapper of the pyminifier plugins, this configs is
    mapping 1:1 with the options of the pyminifier.
    '''

    def __init__(self):
        self.tabs = False
        self.use_nonlatin = True
        self.obfuscate = True
        self.obf_classes = True
        self.obf_functions = True
        self.obf_variables = True
        self.obf_import_methods = True
        self.obf_builtins = True


def minify(file, obfuscate_src=False):
    config = MinifyConfig()

    if obfuscate_src:
        obfuscate.obfuscation_machine(identifier_length=1)

    # Get the module name from the path
    module = os.path.split(file)[1]
    module = '.'.join(module.split('.')[:-1])
    source = open(file).read()

    tokens = token_utils.listified_tokenizer(source)
    source = minification.minify(tokens, config)
    # Have to re-tokenize for obfucation
    tokens = token_utils.listified_tokenizer(source)
    # Perform obfuscation if the related option were set
    if obfuscate_src:
        obfuscate.obfuscate(module, tokens, config)

    # Convert back to text
    result = token_utils.untokenize(tokens)

    return result