"""Module containing the commandline interface for the carconnectivity influxdb plugin."""
from __future__ import annotations
from typing import TYPE_CHECKING

import logging

from carconnectivity.carconnectivity_base import CLI

from carconnectivity_plugins.influxdb._version import __version__

if TYPE_CHECKING:
    pass

LOG = logging.getLogger("carconnectivity-influxdb")


def main() -> None:
    """
    Entry point for the car connectivity influxdb application.

    This function initializes and starts the command-line interface (CLI) for the
    car connectivity application using the specified logger and application name.
    """
    cli: CLI = CLI(logger=LOG, name='carconnectivity-influxdb', description='Commandline Interface to interact with Car Services of various brands',
                   subversion=__version__)
    cli.main()
