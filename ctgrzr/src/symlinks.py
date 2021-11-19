from collections import deque

from .logger import get_logger


def search_symlinks_in_directory(root):
    get_logger().info(f'Checking for symlinks in "{root}"')
    dq = deque([root])
    while dq:
        path = dq.popleft()
        if path.is_dir():
            for child in path.iterdir():
                dq.appendleft(child)
        if path.is_symlink():
            yield path


def search_symlinks_in_directories(paths):
    for path in paths:
        if path.is_symlink():
            yield path
        if path.is_dir():
            yield from search_symlinks_in_directory(path)
