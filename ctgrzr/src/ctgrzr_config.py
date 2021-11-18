import yaml
from pathlib import Path
from collections import Counter

from .env import CTGRZR_CONFIG_DEFAULT
from .exception import AppException
from .logger import get_logger
from .utils import to_absolute_path, validate_writable_directory

EMPTY_CTGRZR_CONFIG = {}


def validate_config(config):
    for category, paths in config.items():
        locations = Counter(paths)
        duplicate_locations = [loc for loc, cnt in locations.items() if cnt > 1]
        if duplicate_locations:
            raise AppException(
                f'Category "{category}" has duplicate paths: {(", ".join(duplicate_locations))}'
            )
    return config


def serialize_config(config):
    for category, paths in config.items():
        config[category] = [str(path) for path in paths]
    return config


def deserialize_config(config):
    for category, paths in config.items():
        config[category] = [to_absolute_path(Path(path)) for path in paths]
    return config


def load_config(config_path):
    get_logger().info("Loading config")
    if config_path.exists():
        with open(config_path) as f:
            data = f.read()
            config = yaml.safe_load(data) if data.strip() else EMPTY_CTGRZR_CONFIG
            config = validate_config(config)
            return deserialize_config(config)
    get_logger().info("Config not specified, using default config")
    default_manifest_directory = to_absolute_path(Path(CTGRZR_CONFIG_DEFAULT)).parent
    if not default_manifest_directory.exists():
        get_logger().warning(
            f'Default directory "{default_manifest_directory}" not found, creating'
        )
        default_manifest_directory.mkdir(parents=True)
    parent_path = config_path.parent
    validation_error = validate_writable_directory(parent_path)
    if validation_error:
        raise AppException(validation_error)
    return EMPTY_CTGRZR_CONFIG


def save_config(config_path, config):
    get_logger().info("Saving config")
    with open(config_path, "w") as f:
        f.write(yaml.dump(serialize_config(config)))


def add_path(config, path, categories, force):
    for category in categories:
        if category not in config:
            config[category] = []
        if path in config[category]:
            if force:
                config[category] = [
                    entry for entry in config[category] if entry != path
                ]
            else:
                raise AppException(
                    f'Path "{path}" already present in category "{category}"'
                )
        config[category].append(str(path))
    return config


def remove_path(config, path, categories):
    non_existing_categories = [
        category for category in categories if category not in config
    ]
    if non_existing_categories:
        raise AppException(
            f'Categories {", ".join(non_existing_categories)} don\'t exist'
        )
    categories = categories if categories is not None else config.keys()
    for category in categories:
        config[category] = [entry for entry in config[category] if entry != path]
    return config
