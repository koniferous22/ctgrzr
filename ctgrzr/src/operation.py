import yaml
import os
import sys
from pathlib import Path
from subprocess import run, PIPE

from .exception import AppException
from .logger import get_logger


def validate_operations_config(operations_config):
    get_logger().info("Validating operations config")
    if len(operations_config) < MINIMAL_OPERATIONS_CONFIG_SIZE:
        raise AppException(
            f'Operations config, expected minimum "{MINIMAL_OPERATIONS_CONFIG_SIZE}" keys in the config'
        )
    for category, command in operations_config.items():
        if "{}" not in command:
            raise AppException(
                f'Operations config - category "{category}"'
                + 'Expected templated command with "{}" '
                + f'got "{command}"'
            )
    return operations_config


# This assumes that I'm distinguishing at least between 2 buckets
MINIMAL_OPERATIONS_CONFIG_SIZE = 2


def load_operations_config(operations_path, *, validate_expected_keys=None):
    get_logger().info(f'Loading operations config from "{operations_path}"')
    operations_config = None
    if not operations_path.exists():
        raise AppException(f'Operations config "{operations_path}" does not exist')
    if not os.access(operations_path, os.R_OK):
        raise AppException(f'Operations config "{operations_path}" is not readable')
    with open(operations_path) as f:
        data = f.read()
        operations_config = yaml.safe_load(data)
        operations_config = validate_operations_config(operations_config)
    if operations_config is None:
        raise AppException("Unable to load config")
    if validate_expected_keys and set(operations_config.keys()) != set(
        validate_expected_keys
    ):
        operations_config_categories = set(operations_config.keys())
        expected_categories = set(validate_expected_keys)
        message_lines = [
            f'Invalid operations config - "{operations_path}"',
        ]
        missing_categories = expected_categories - operations_config_categories
        redundant_categories = operations_config_categories - expected_categories
        if missing_categories:
            message_lines += ["Missing categories"] + [
                f"* {category}" for category in missing_categories
            ]
        if redundant_categories:
            message_lines += ["Redundant categories"] + [
                f"* {category}" for category in redundant_categories
            ]
        raise AppException("\n".join(message_lines))
    return operations_config


def run_command(command, *, should_redirect_to_stdout=False, check=False):
    get_logger().info(
        f'Running command "{command}" - {"exit" if check  else "continue"} on failure'
    )
    stdout = sys.stdout if should_redirect_to_stdout else PIPE
    completed_process = run(command, shell=True, stdout=stdout, check=check)
    process_output = (
        None if should_redirect_to_stdout else completed_process.stdout.decode("utf-8")
    )
    return (completed_process.returncode, process_output)
