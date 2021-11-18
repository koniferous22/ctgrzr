from src.cli import cli, get_arg_parser
from src.logger import get_logger, set_logging_level
from src.exception import AppException
import traceback
import sys
import logging


def main():
    try:
        parser = get_arg_parser()
        args = parser.parse_args()
        if args.verbose:
            set_logging_level(logging.INFO)
        elif args.quiet:
            set_logging_level(logging.ERROR)
        cli_result = cli(args)
        exit(cli_result)
    except AppException as e:
        get_logger().error(e)
        if args.verbose:
            traceback.print_exc(file=sys.stdout)
        exit(1)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        exit(2)


if __name__ == "__main__":
    main()
