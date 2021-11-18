import os


def to_absolute_path(p):
    return p.expanduser().resolve()


def validate_writable_directory(directory_path):
    if not directory_path.exists():
        return f'Parent path "{directory_path}" does not exist'
    if not directory_path.is_dir():
        return f'Parent path "{directory_path}" is not a directory'
    if not os.access(directory_path, os.W_OK):
        return f'No writable permissions in the "{directory_path}" directory'
