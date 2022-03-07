import os
import sys
import textwrap

from pathlib import Path
from typing import Any

from converters import cast_to_shell
from loaders import load_path, get_definitions



SOURCEPY_HOME = Path(os.environ.get('SOURCEPY_HOME', Path.home() / '.sourcepy'))
SOURCEPY_BIN = Path(__file__).resolve().parent


def make_var(name: str, value: Any) -> str:
    value, typedef = cast_to_shell(value)
    var_def = textwrap.dedent(f"""\
            declare {('-g ' + typedef).strip()} {name}
            {name}={value}
    """)
    return var_def


def make_fn(name: str, runner_name: str) -> str:
    fn_def = textwrap.dedent(f"""\
        {name}() {{
            {runner_name} {name} "$@"
        }}
    """)
    return fn_def


def make_runner(runner_name: str, module_path: Path) -> str:
    runner = textwrap.dedent(f"""\
        {runner_name}() {{
            {sys.executable} {SOURCEPY_BIN}/run.py {module_path} "$@"
        }}
    """)
    return runner


def escape(path: Path) -> str:
    escaped = str(path)
    for c in '. /':
        escaped = escaped.replace(c, '_')
    return escaped


def build_stub(module_path: Path) -> str:
    stub_contents = []

    module = load_path(module_path)
    stub_title = f'SourcePy stub for {module.__name__} ({module_path})'
    stub_contents.append(textwrap.dedent(f"""\
        ######{"#" * len(stub_title)}######
        ##### {stub_title} #####
        ######{"#" * len(stub_title)}######
    """))

    runner_name = f'_sourcepy_run_{hash(module)}'
    runner = make_runner(runner_name, module_path)
    stub_contents.append('# SourcePy runner')
    stub_contents.append(runner)

    stub_contents.append('\n# Definitions')
    for d in get_definitions(module):
        full_name = d['parents'] + [d['name']]
        full_name = '.'.join(full_name)
        if d['type'] == 'function':
            fn_def = make_fn(full_name, runner_name)
            stub_contents.append(fn_def)
        elif d['type'] == 'variable':
            var_def = make_var(full_name, d['value'])
            stub_contents.append(var_def)
    stub = '\n'.join(stub_contents)
    return stub


def write_stub_file(stub_contents: str, stub_name: str) -> Path:
    stub_file = SOURCEPY_HOME / 'stubs' / stub_name
    stub_file.parent.mkdir(parents=True, exist_ok=True)
    with open(stub_file, 'w') as f:
        f.write(stub_contents)
    return stub_file


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("sourcepy: not enough arguments")
    module_path = Path(sys.argv[1]).resolve()
    stub_contents = build_stub(module_path)
    stub_name = escape(module_path) + '.sh'
    stub_file = write_stub_file(stub_contents, stub_name)
    print(stub_file)
