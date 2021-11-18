from argparse import ArgumentParser
from collections import deque
from pathlib import Path
from InquirerPy import inquirer
from InquirerPy.base import Choice
import os

from .ctgrzr_config import (
    EMPTY_CTGRZR_CONFIG,
    add_path,
    load_config,
    remove_path,
    save_config,
)
from .env import resolve_config_path
from .exception import AppException
from .logger import get_logger
from .operation import load_operations_config, run_command
from .utils import to_absolute_path


def get_arg_parser():
    parser = ArgumentParser("ctgrzr")
    parser.add_argument("-c", "--config", help="Path categories config")
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("-v", "--verbose", action="store_true", help="verbose")
    verbosity_group.add_argument("-q", "--quiet", action="store_true", help="quiet")
    subparsers = parser.add_subparsers(title="commands", dest="command", required=True)
    parser_add = subparsers.add_parser("add", help="Add path to category")
    parser_add.add_argument("path", help="Path")
    parser_add.add_argument("categories", help="Categories", nargs="+")
    parser_add.add_argument(
        "-f", "--force", help="Overwrite if exists", action="store_true"
    )
    parser_remove = subparsers.add_parser("remove", help="Removes tag from repo")
    parser_remove.add_argument("path", help="Path")
    parser_remove.add_argument("categories", help="categories", nargs="*")
    parser_interactive = subparsers.add_parser(
        "interactive", help="Walks the FS interactively"
    )
    parser_interactive.add_argument(
        "operations", help="File containing yaml definition of operations to apply"
    )
    parser_interactive.add_argument("path", nargs="?", help="Root path")
    parser_apply = subparsers.add_parser(
        "apply", help="Applies operations, by definfed YAML file"
    )
    parser_apply.add_argument(
        "operations", help="File containing yaml definitions of operations to apply"
    )
    parser_autoadd = subparsers.add_parser(
        "autoadd",
        help="Automatically replicates categorization from another config file",
    )
    parser_autoadd.add_argument(
        "template", help="Template config file (same as for -c option"
    )
    parser_validate = subparsers.add_parser(
        "validate", help="Checks if paths exist on current filesystem"
    )
    parser_validate.add_argument("categories", help="Categories", nargs="*")

    return parser


# Interactive walk: prompt if config path exists


def add(config, path, categories, *, force=False):
    if not categories:
        raise AppException("No category specified")
    if not path.exists():
        raise AppException(f'Path "{path}" does not exist')
    if not (path.is_file() or path.is_dir()):
        raise AppException(f'Path "{path}" should be regular file or directory')
    config = add_path(config, path, categories, force)
    return 0, True


def autoadd(config, template_config):
    config_entries_by_paths = [
        (path, category)
        for category, paths in template_config.items()
        for path in paths
    ]
    template_config_by_path = {}
    for path, category in config_entries_by_paths:
        if path not in template_config_by_path:
            template_config_by_path[path] = []
        template_config_by_path[path].append(category)
    for path, categories in template_config_by_path.items():
        should_add = path.exists() and (path.is_file or path.is_dir())
        if should_add:
            add(config, path, categories)
    return 0, True


def apply(config, operations_config):
    strict = False
    for category, paths in config.items():
        command_template = operations_config[category]
        for path in paths:
            try:
                command = command_template.replace("{}", str(path))
                run_command(command, should_redirect_to_stdout=True, check=True)
            except AppException as e:
                if strict:
                    raise e
                get_logger().error(e)
    return 0, False
    # TODO configure failing
    # TODO add strict option


def interactive(config, operations_config, root):
    dq = deque([root])
    operations = operations_config.keys()
    # TODO move to options
    SHOULD_INCLUDE_SYMLINKS = False
    SHOULD_RECURSE = True
    dir_choices = list(operations)
    file_choices = list(operations)
    if SHOULD_RECURSE:
        dir_choices.append("Step-into")
    dir_choices += [Choice(value=None, name="Skip"), "Exit"]
    file_choices += [Choice(value=None, name="Skip"), "Exit"]
    while dq:
        path = Path(dq.popleft())
        should_process_file = path.is_file() or (
            path.is_symlink() and SHOULD_INCLUDE_SYMLINKS
        )
        # TODO add log when read permissions are missing
        should_process_file = should_process_file and os.access(path, os.R_OK)
        if should_process_file:
            action = inquirer.select(
                message=f'"{path}" - select an action:',
                choices=file_choices,
                default="Skip",
            ).execute()
            if action == "Exit":
                return 0, True
            elif action is not None:
                add(config, path, [action])

        elif path.is_symlink():
            print("Skipping symlink")
            # TODO add log when read permissions are missing
        elif path.is_dir() and os.access(path, os.R_OK):
            action = inquirer.select(
                message=f'"{path}" - select an action:',
                choices=dir_choices,
                default="Skip",
            ).execute()
            if action == "Exit":
                return 0, True
            elif SHOULD_RECURSE and action == "Step-into":
                for child in path.iterdir():
                    dq.appendleft(child)
            elif action is not None:
                add(config, path, [action])
    return 0, True


def remove(config, path, categories):
    if not categories:
        raise AppException("No category specified")
    config = remove_path(config, path, categories)
    return 0, True


def validate(config, categories):
    validation_errors = []
    categories = categories if categories is not None else config.keys()
    for category, paths in config.items():
        if category not in categories:
            continue
        for path in paths:
            if not path.exists():
                validation_errors.append(
                    f'Category "{category}" - Path "{path}" does not exist'
                )
            if not (path.is_file() and path.is_dir()):
                validation_errors.append(
                    f'Category "{category}" - Path "{path}" should be regular file or directory'
                )
    if validation_errors:
        raise AppException(
            "\n".join(
                ["Following errors were encountered"]
                + [f"* {error}" for error in validation_errors]
            )
        )
    return 0, False


def cli(args):
    get_logger().info("Running in verbose mode")
    cli_result = 0
    config_path = resolve_config_path(args.config)
    should_write_config = False
    config = None
    if args.command == "add":
        path = to_absolute_path(Path(args.path))
        config = load_config(config_path)
        cli_result, should_write_config = add(
            config, path, args.categories, force=args.force
        )
    elif args.command == "apply":
        config = load_config(config_path)
        operations_config = load_operations_config(
            to_absolute_path(Path(args.operations)),
            validate_expected_keys=config.keys(),
        )
        cli_result, should_write_config = apply(config, operations_config)
    elif args.command == "autoadd":
        tempalte_config_path = args.template
        if tempalte_config_path == config_path:
            raise AppException("Config and template config path cannot be same")
        config = load_config(config_path)
        template_config = load_config(config_path)
        cli_result, should_write_config = autoadd(config, template_config)
    elif args.command == "interactive":
        should_continue_despite_possible_overwrite = (
            config_path.exists()
            and inquirer.confirm(
                message=f'Config "{config_path}" already exist, do you want to continue and overwrite?',
                default=False,
            ).execute()
        )
        if not should_continue_despite_possible_overwrite:
            return 0
        config = EMPTY_CTGRZR_CONFIG
        operations_config = load_operations_config(
            to_absolute_path(Path(args.operations))
        )
        root_path = Path(args.path) if args.path is not None else Path(os.getcwd())
        root_path = to_absolute_path(root_path)
        cli_result, should_write_config = interactive(
            config, operations_config, root_path
        )

    elif args.command == "remove":
        path = to_absolute_path(Path(args.path))
        config = load_config(config_path)
        cli_result, should_write_config = remove(config, path, args.categories)
    elif args.command == "validate":
        config = load_config(config_path)
        cli_result, should_write_config = validate(config, args.categories)
    else:
        raise AppException(f'Unknown command "{args.command}"')
    if should_write_config:
        save_config(config_path, config)
    return cli_result


# TODO logging
# TODO test everything except "interactive"
# TODO format code
# TODO code structure

# 3. walk file-system

# * skip symlinks
# * skip symlink check after categorization

# Process node
# * skip: no permissions, symlinks
# * skip directories without list permission
# * executable dir permission is just for cd
# * no recurse option
