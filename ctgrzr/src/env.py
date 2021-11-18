from os import environ
from pathlib import Path

from .logger import get_logger

CTGRZR_CONFIG_DEFAULT = "~/.ctgrzr/config.yaml"
CTGRZR_CONFIG_ENV = "CTGRZR_CONFIG"


def get_config_path_as_string(config_from_cli):
    get_logger().info(f'Resolving config path (CLI arg: "{config_from_cli}"')
    if config_from_cli is not None:
        return config_from_cli
    manifest_from_env = environ.get(CTGRZR_CONFIG_ENV)
    if manifest_from_env:
        return manifest_from_env
    return CTGRZR_CONFIG_DEFAULT


def resolve_config_path(config_from_cli):
    return Path(get_config_path_as_string(config_from_cli)).expanduser().resolve()
