"""Toronto Street View Panorama Counter

A tool to count all Google Street View panoramas within the City of Toronto boundary
using road network sampling and the Google Street View Image Metadata API.
"""

from .cli import cli

__version__ = "0.1.0"
__all__ = ["cli"]


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
