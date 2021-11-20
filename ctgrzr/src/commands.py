from collections import deque

from InquirerPy import inquirer
from InquirerPy.base import Choice

from .symlinks import search_symlinks_in_directories

from .ctgrzr_config import (
    add_path,
    get_paths_from_config,
    remove_path,
    transform_config_by_path,
)
from .exception import AppException
from .fs_walk import should_process_path, ProcessPath, DequeOperation, process_path
from .logger import get_logger
from .operation import run_command


def add(config, path, categories, *, force=False, allow_symlink=False):
    get_logger().info('Running "add" command')
    if not categories:
        raise AppException("No category specified")
    if not path.exists():
        raise AppException(f'Path "{path}" does not exist')
    if not (path.is_file() or path.is_dir()):
        raise AppException(f'Path "{path}" should be regular file or directory')

    if not allow_symlink and path.is_symlink():
        raise AppException(f'Path "{path}" cannot be a symlink, otherwise run with "-s" option' )
    config = add_path(config, path, categories, force)
    return 0, True


def autoadd(config, template_config, *, force=False, allow_symlinks=False):
    get_logger().info('Running "autoadd" command')
    template_config_by_path = transform_config_by_path(template_config)
    for path, categories in template_config_by_path.items():
        should_add = path.exists() and (path.is_file() or path.is_dir())
        if should_add:
            add(config, path, categories, force=force, allow_symlink=allow_symlinks)
    return 0, True


def apply(config, operations_config, *, strict=True):
    get_logger().info('Running "apply" command')
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


def interactive(
    config,
    operations_config,
    root_paths,
    *,
    initial_config,
    max_depth,
    should_include_symlinks=False,
):
    get_logger().info('Running "interactive" command')
    dq = deque([ProcessPath(root_path) for root_path in root_paths])
    categories = operations_config.keys()
    ctx = dict(config=config, dq=dq, categories=categories, current_depth=0)
    initial_config_by_path = (
        {} if initial_config is None else transform_config_by_path(initial_config)
    )
    should_continue = True
    processed_items = 0
    while should_continue and dq:
        dq_operation = dq.popleft()
        if dq_operation == DequeOperation.DECREMENT_DEPTH:
            ctx["current_depth"] -= 1
        elif isinstance(dq_operation, ProcessPath):
            path = dq_operation.path
            if should_process_path(path, should_include_symlinks):
                ctx["path"] = path
                should_continue, ctx = process_path(
                    ctx,
                    initial_config_by_path=initial_config_by_path,
                    max_depth=max_depth,
                )
                processed_items += 1
        else:
            raise AppException(f'Invalid operation "{dq_operation}"')
    if processed_items == 0:
        get_logger().warning("No items were actually processed")

    return 0, True


def remove(config, path, categories, *, force=False):
    get_logger().info('Running "remove" command')
    if not categories:
        raise AppException("No category specified")
    config = remove_path(config, path, categories, force)
    return 0, True


def search_symlinks(config, *, interactive, should_use_logger):
    get_logger().info('Running "search_symlinks" command')
    paths = get_paths_from_config(config)
    if interactive:
        symlink_paths = set([path for path in paths if path.is_symlink()])
        all_directory_paths = [path for path in paths if path.is_dir()]
        paths = inquirer.checkbox(
            message="Choose relevant directories",
            choices=[Choice(path, enabled=True) for path in all_directory_paths],
        ).execute()
        paths = set(paths) | symlink_paths
    logger = get_logger()
    output = logger.warning if should_use_logger else print
    for symlink in search_symlinks_in_directories(paths):
        output(f'Symlink found: "{symlink}"')
    return 0, False


def validate(config, categories):
    get_logger().info('Running "validate" command')
    validation_errors = []
    if not categories:
        get_logger().info('No categories specified, assuming all')
        categories = list(config.keys())
    for category, paths in config.items():
        if category not in categories:
            continue
        for path in paths:
            if not path.exists():
                validation_errors.append(
                    f'Category "{category}" - Path "{path}" does not exist'
                )
            if not (path.is_file() or path.is_dir()):
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
