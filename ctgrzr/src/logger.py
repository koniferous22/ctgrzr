import logging
from pathlib import PurePosixPath


class LogFormatter(logging.Formatter):

    grey = "\x1b[38;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def init_logger():
    logger_ = logging.getLogger(PurePosixPath(__file__).name)
    logger_.setLevel(logging.WARNING)
    # create console handler with a higher log level
    ch_ = logging.StreamHandler()
    ch_.setLevel(logging.WARNING)
    ch_.setFormatter(LogFormatter())
    logger_.addHandler(ch_)
    return logger_, ch_


logger, ch = init_logger()


def set_logging_level(level):
    ch.setLevel(level)
    logger.setLevel(level)


def get_logger():
    return logger
