from argparse import ArgumentParser
from pathlib import Path
from InquirerPy import inquirer
import os

from .commands import (
    add,
    autoadd,
    apply,
    interactive,
    remove,
    search_symlinks,
    validate,
)
from .ctgrzr_config import load_config, save_config
from .env import resolve_config_path
from .exception import AppException
from .logger import get_logger
from .operation import load_operations_config
from .utils import to_absolute_path


def get_arg_parser():
    parser = ArgumentParser("ctgrzr")
    parser.add_argument("-c", "--config", help="Path to categories config")
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("-v", "--verbose", action="store_true", help="verbose")
    verbosity_group.add_argument("-q", "--quiet", action="store_true", help="quiet")
    subparsers = parser.add_subparsers(title="commands", dest="command", required=True)
    parser_add = subparsers.add_parser("add", help="Add path to category")
    parser_add.add_argument(
        "-f", "--force", help="Overwrite if exists", action="store_true"
    )
    parser_add.add_argument(
        "-s", "--symlink", help="Allow symlink", action="store_true"
    )
    parser_add.add_argument("path", help="Path")
    parser_add.add_argument("categories", help="Categories", nargs="+")
    parser_apply = subparsers.add_parser(
        "apply", help="Applies operations, by definfed YAML file"
    )
    parser_apply.add_argument(
        "-s", "--strict", action="store_true", help="Fails on 1st failed operation"
    )
    parser_apply.add_argument(
        "operations", help="File containing yaml definitions of operations to apply"
    )
    parser_autoadd = subparsers.add_parser(
        "autoadd",
        help="Automatically replicates categorization from another config file",
    )
    parser_autoadd.add_argument(
        "-f", "--force", help="Overwrite if exists", action="store_true"
    )
    parser_autoadd.add_argument(
        "-s", "--symlinks", help="Allow symlinks", action="store_true"
    )
    parser_autoadd.add_argument(
        "template", help="Template config file (same as for -c option"
    )
    parser_interactive = subparsers.add_parser(
        "interactive", help="Walks the FS interactively"
    )
    parser_interactive.add_argument(
        "operations", help="File containing yaml definition of operations to apply"
    )
    parser_interactive.add_argument(
        "--max-depth", help="Max depth when walking the FS", type=int
    )
    parser_interactive.add_argument(
        "--no-recurse",
        help="Alias for --max-depth=1",
        action="store_const",
        dest="max_depth",
        const=1,
    )
    parser_interactive.add_argument(
        "-s", "--symlinks", help="Include symlinks", action="store_true"
    )
    parser_interactive.add_argument(
        "-m", "--multiple", help="Multiple choice", action="store_true"
    )
    parser_interactive.add_argument(
        "--skip-symlink-check",
        help="Don't check for symlinks after categorization",
        action="store_true",
    )
    parser_interactive.add_argument(
        "paths", nargs="*", help="Root path(s), defaults to $PWD if skipped"
    )
    parser_remove = subparsers.add_parser("remove", help="Removes tag from repo")
    parser_remove.add_argument('-f', '--force', action='store_true', help='No error if path is not found')
    parser_remove.add_argument("path", help="Path")
    parser_remove.add_argument("categories", help="categories", nargs="*")
    parser_search_symlinks = subparsers.add_parser(
        "search-symlinks", help="Checks if any paths in config contains symlinks"
    )
    parser_search_symlinks.add_argument("-i", "--interactive", action="store_true")
    parser_validate = subparsers.add_parser(
        "validate", help="Checks if paths exist on current filesystem"
    )
    parser_validate.add_argument("categories", help="Categories", nargs="*")

    return parser


def cli(args):
    get_logger().info("Running in verbose mode")
    cli_result = 0
    config_path = resolve_config_path(args.config)
    should_write_config = False
    config = load_config(config_path)
    if args.command == "add":
        path = to_absolute_path(Path(args.path))
        cli_result, should_write_config = add(
            config, path, args.categories, force=args.force, allow_symlink=args.symlink
        )
    elif args.command == "apply":
        operations_config = load_operations_config(
            to_absolute_path(Path(args.operations)),
            validate_expected_keys=config.keys(),
        )
        cli_result, should_write_config = apply(
            config, operations_config, strict=args.strict
        )
    elif args.command == "autoadd":
        template_config_path = to_absolute_path(Path(args.template))
        if template_config_path == config_path:
            raise AppException("Config and template config path cannot be same")
        template_config = load_config(template_config_path)
        cli_result, should_write_config = autoadd(config, template_config, force=args.force, allow_symlinks=args.symlinks)
    elif args.command == "interactive":
        is_possible_overwrite_due_to_existing_config = (
            config_path.exists()
            and inquirer.confirm(
                message=f'Config "{config_path}" already exist, do you want to continue and overwrite?',
                default=False,
            ).execute()
        )
        initial_config = (
            config if is_possible_overwrite_due_to_existing_config else None
        )
        operations_config = load_operations_config(
            to_absolute_path(Path(args.operations))
        )
        root_paths = (
            [Path(path) for path in args.paths] if args.paths else [Path(os.getcwd())]
        )
        root_paths = [to_absolute_path(root_path) for root_path in root_paths]
        cli_result, should_write_config = interactive(
            config,
            operations_config,
            root_paths,
            initial_config=initial_config,
            max_depth=args.max_depth,
            should_include_symlinks=args.symlinks,
        )
        should_search_for_symlinks = (not args.skip_symlink_check) and inquirer.confirm(
            message="Do you want run symlink check on config file?", default=False
        ).execute()
        if should_search_for_symlinks:
            should_run_interactive = inquirer.confirm(
                message="Do you want to pick which entries to check"
            ).execute()
            search_symlinks(
                config, interactive=should_run_interactive, should_use_logger=True
            )
    elif args.command == "remove":
        path = to_absolute_path(Path(args.path))
        cli_result, should_write_config = remove(config, path, args.categories, force=args.force)
    elif args.command == "search-symlinks":
        cli_result, should_write_config = search_symlinks(
            config, interactive=args.interactive, should_use_logger=False
        )
    elif args.command == "validate":
        cli_result, should_write_config = validate(config, args.categories)
    else:
        raise AppException(f'Unknown command "{args.command}"')
    if should_write_config:
        save_config(config_path, config)
    return cli_result

