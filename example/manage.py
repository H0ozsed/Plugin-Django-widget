#!/usr/bin/env python
"""Command-line entry point for the widget_hub demo project."""

import os
import sys


def main() -> None:
    """Run a Django management command for the demo project."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_project.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
