import argparse
from collections import defaultdict
import inspect

from collections.abc import Callable
from typing import Any

from converters import typecast_factory



POSITIONAL_ONLY = inspect.Parameter.POSITIONAL_ONLY
POSITIONAL_OR_KEYWORD = inspect.Parameter.POSITIONAL_OR_KEYWORD
KEYWORD_ONLY = inspect.Parameter.KEYWORD_ONLY
REQUIRED = 'REQUIRED'


class DynamicArgumentParser(argparse.ArgumentParser):

    def __init__(self, fn: Callable, /, *args: Any, **kwargs: Any) -> None:

        super().__init__(description=inspect.getdoc(fn),
                         prog=fn.__name__, *args, **kwargs)
        self.param_signatures = inspect.signature(fn).parameters
        self.params_meta = defaultdict(list)
        for name, param in self.param_signatures.items():
            kind = param.kind
            self.params_meta[kind].append(param)
            if param.default == inspect._empty:
                self.params_meta[REQUIRED].append(param)
        self.generate_args()

    def generate_args(self) -> None:
        if self.params_meta[POSITIONAL_ONLY]:
            self.generate_positional_only_args()

        if self.params_meta[POSITIONAL_OR_KEYWORD]:
            self.generate_positional_or_keyword_args()

        if self.params_meta[KEYWORD_ONLY]:
            self.generate_keyword_only_args()

    def generate_positional_only_args(self) -> None:
        group = self.add_argument_group('positional only args')
        for param in self.params_meta[POSITIONAL_ONLY]:
            name = param.name
            options = self.generate_arg_options(param)
            group.add_argument(name, **options)

    def generate_positional_or_keyword_args(self) -> None:
        group = self.add_argument_group('positional or keyword args')
        group.add_argument('_positional_or_kw', nargs='*', default=[], help=argparse.SUPPRESS)
        for param in self.params_meta[POSITIONAL_OR_KEYWORD]:
            name = '--' + param.name.replace('_', '-')
            options = self.generate_arg_options(param)
            group.add_argument(name, **options)

    def generate_keyword_only_args(self) -> None:
        group = self.add_argument_group('keyword only args')
        for param in self.params_meta[KEYWORD_ONLY]:
            name = '--' + param.name.replace('_', '-')
            options = self.generate_arg_options(param)
            group.add_argument(name, **options)

    def generate_arg_options(self, param: inspect.Parameter) -> dict[str, Any]:
        options = {}
        helptext = []

        typecast = typecast_factory(param)
        if typecast is not None:
            helptext.append(typecast.__name__)

        # action & type for bools are incompatible
        if param.annotation == bool or isinstance(param.default, bool):
            if param.kind == POSITIONAL_ONLY:
                options['action'] = 'store_true'
            else:
                # this nicer --option / --no-option helper
                # can only be usedwith kwargs
                options['action'] = argparse.BooleanOptionalAction
        elif typecast is not None:
            options['type'] = typecast

        if param.default is not inspect._empty:
            helptext.append(f'(default: {param.default})')
        else:
            helptext.append('(required)')

        if options.get('action') != argparse.BooleanOptionalAction:
            options['default'] = argparse.SUPPRESS
        if param.kind == POSITIONAL_OR_KEYWORD:
            options['metavar'] = f'/ {param.name}'
        if param.kind == KEYWORD_ONLY:
            options['metavar'] = ''

        options['help'] = ' '.join(helptext)
        return options

    def parse_args(self, *args, **kwargs):
        cmd_args = vars(super().parse_args(*args, **kwargs))
        args = []
        kwargs = {}
        for param in self.params_meta[POSITIONAL_ONLY]:
            value = cmd_args[param.name]
            args.append(value)
        for param in self.params_meta[POSITIONAL_OR_KEYWORD]:
            if param.name in cmd_args:
                kwargs[param.name] = cmd_args[param.name]
            else:
                try: # no idea if this is sane
                    raw_value = cmd_args['_positional_or_kw'].pop(0)
                    kwargs[param.name] = raw_value
                    cmd_args[param.name] = raw_value #
                except IndexError:
                    pass
        for param in self.params_meta[KEYWORD_ONLY]:
            if param.name in cmd_args:
                kwargs[param.name] = cmd_args[param.name]

        for param in self.params_meta[REQUIRED]:
            if param.name not in cmd_args:
                self.error(f'the following arguments are required: {param.name}')

        return args, kwargs
