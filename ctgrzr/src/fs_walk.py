from enum import Enum
from InquirerPy import inquirer
from InquirerPy.base import Choice
import os
from pathlib import Path

from .ctgrzr_config import add_path
from .exception import AppException
from .logger import get_logger


def should_process_path(path: Path, should_include_symlinks_as_files):
    if not os.access(path, os.R_OK):
        return False
    is_symlink = path.is_symlink()
    if path.is_file():
        return True
    if is_symlink:
        if should_include_symlinks_as_files:
            return True
        get_logger().info(f'Skipping symlink "{path}"')
    return path.is_dir()


class CallableEnum(Enum):
    def __call__(self, *args, **kwargs):
        return self.value(*args, **kwargs)


class ProcessPath:
    def __init__(self, path):
        self.path = path


class DequeOperation(CallableEnum):
    DECREMENT_DEPTH = 0
    PROCESS_PATH = ProcessPath


class CategoryChoice:
    def __init__(self, name):
        self.name = name


class FsWalkOperation(CallableEnum):

    PICK_CATEGORIES = 0
    PICK_SINGLE_CATEGORY = CategoryChoice
    STEP_INTO = 2
    STEP_OUT = 3
    SKIP = 4
    EXIT = 5


def process_path(
    ctx, *, is_multi_category=False, max_depth=None, initial_config_by_path={}
):
    get_logger().info(
        f"Running with following options: multi = {is_multi_category}, max_depth = {max_depth}"
    )
    config = ctx["config"]
    dq = ctx["dq"]
    path = ctx["path"]
    categories = ctx["categories"]
    current_depth = ctx["current_depth"]
    if path in initial_config_by_path:
        get_logger().info(f'Skipping path "{path}" as it already is in configuration')
        return True, ctx
    list_choices = [
        choice
        for choice in [
            Choice(name="Skip", value=FsWalkOperation.SKIP),
            Choice(name="Step-into", value=FsWalkOperation.STEP_INTO)
            if path.is_dir() and (max_depth is None or current_depth < max_depth)
            else None,
            Choice(name="Step-out", value=FsWalkOperation.STEP_OUT)
            if current_depth > 0
            else None,
            Choice(name="Exit", value=FsWalkOperation.EXIT),
        ]
        if choice is not None
    ]
    action = None
    selected_categories = []
    message = f'"{path}" - select an action:'
    if is_multi_category:
        multi_category_choices = [
            Choice("Choose category", value=FsWalkOperation.PICK_CATEGORIES)
        ] + list_choices
        action = inquirer.select(
            message=message, choices=multi_category_choices, default=None
        ).execute()
        if action == FsWalkOperation.PICK_CATEGORIES:
            selected_categories = inquirer.checkbox(
                message="Pick categories", choices=[category for category in categories]
            )
    else:
        single_category_choices = [
            Choice(
                name=f'Category "{category}"',
                value=FsWalkOperation.PICK_SINGLE_CATEGORY(category),
            )
            for category in categories
        ] + list_choices
        action = inquirer.select(
            message=message, choices=single_category_choices, default=None
        ).execute()
        if isinstance(action, CategoryChoice):
            selected_categories = [action.name]
    if action == FsWalkOperation.EXIT:
        get_logger().info("Exit action")
        return False, ctx
    if action == FsWalkOperation.STEP_INTO:
        get_logger().info("Step-into action")
        if max_depth is None or current_depth < max_depth:
            dq.appendleft(DequeOperation.DECREMENT_DEPTH)
            for child in path.iterdir():
                dq.appendleft(DequeOperation.PROCESS_PATH(child))
            ctx["current_depth"] = current_depth + 1
            return True, ctx
    if action == FsWalkOperation.STEP_OUT:
        get_logger().info("Step-out action")
        while dq[0] != DequeOperation.DECREMENT_DEPTH:
            dq.popleft()
        return True, ctx
    if action == FsWalkOperation.PICK_CATEGORIES or isinstance(action, CategoryChoice):
        get_logger().info(f'Adding path "{path}" to categories {", ".join(categories)}')
        add_path(config, path, selected_categories, False)
        return True, ctx
    if action == FsWalkOperation.SKIP:
        get_logger().info("Skip action")
        return True, ctx
    raise AppException(f'Invalid action "{action}"')
