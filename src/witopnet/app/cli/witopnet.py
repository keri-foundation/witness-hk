# -*- encoding: utf-8 -*-
"""
witopnet.app.cli module

"""

import multicommand
from hio.base import doing
from hio.help import ogler

from witopnet.app.cli import commands

logger = ogler.getLogger()


def main():
    """Entry point for the witopnet CLI.

    Builds the argument parser from the commands package, dispatches to the
    appropriate subcommand handler, and runs the resulting doers under a Doist
    event loop. Prints usage if no subcommand is given.
    """
    parser = multicommand.create_parser(commands)
    args = parser.parse_args()

    if not hasattr(args, "handler"):
        parser.print_help()
        return

    try:
        doers = args.handler(args)
        tock = 0.00125
        doist = doing.Doist(limit=0.0, tock=tock, real=True)
        doist.do(doers=doers)

    except Exception as ex:
        import os

        if os.getenv("DEBUG_WITOPNET"):
            import traceback

            traceback.print_exc()
        else:
            print(f"ERR: {ex}")
        return -1


if __name__ == "__main__":
    main()
