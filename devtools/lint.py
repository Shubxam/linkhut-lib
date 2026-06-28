"""Run linting and formatting tools (codespell, ruff, ty) for the project."""

import argparse
import subprocess
import sys

from rich import get_console, reconfigure
from rich import print as rprint

# Update as needed.
SRC_PATHS = ['tests', 'src']
DOC_PATHS = ['docs', 'readme.md']


reconfigure(
    emoji=not get_console().options.legacy_windows
)  # No emojis on legacy windows.


def main() -> int:
    """Run all configured lint/format/type-check steps and report a summary."""
    parser = argparse.ArgumentParser(description='Run linting and formatting.')
    # CI should not modify files: check-only mode fails on any issue instead of
    # silently fixing it, so unformatted code can't slip through.
    parser.add_argument(
        '--check', action='store_true', help='Check only, without modifying files.'
    )
    args = parser.parse_args()

    rprint()

    errcount = 0
    if args.check:
        errcount += run(
            [
                'uv',
                'run',
                'codespell',
                *SRC_PATHS,
                *DOC_PATHS,
            ]
        )
        errcount += run(['uv', 'run', 'ruff', 'check', *SRC_PATHS])
        errcount += run(['uv', 'run', 'ruff', 'format', '--check', *SRC_PATHS])
        errcount += run(['uv', 'run', 'ty', 'check', *SRC_PATHS])
    else:
        errcount += run(
            [
                'uv',
                'run',
                'codespell',
                '--write-changes',
                *SRC_PATHS,
                *DOC_PATHS,
            ]
        )
        errcount += run(['uv', 'run', 'ruff', 'check', '--fix', *SRC_PATHS])
        errcount += run(['uv', 'run', 'ruff', 'format', *SRC_PATHS])
        errcount += run(['uv', 'run', 'ty', 'check', *SRC_PATHS])

    rprint()

    if errcount != 0:
        rprint(f'[bold red]:x: Lint failed with {errcount} errors.[/bold red]')
    else:
        rprint('[bold green]:white_check_mark: Lint passed![/bold green]')
    rprint()

    return errcount


def run(cmd: list[str]) -> int:
    """Execute a single lint step and return its exit status."""
    rprint()
    rprint(f'[bold green]>> {" ".join(cmd)}[/bold green]')
    errcount = 0
    try:
        subprocess.run(cmd, text=True, check=True)
    except KeyboardInterrupt:
        rprint('[yellow]Keyboard interrupt - Cancelled[/yellow]')
        errcount = 1
    except subprocess.CalledProcessError as e:
        rprint(f'[bold red]Error: {e}[/bold red]')
        errcount = 1

    return errcount


if __name__ == '__main__':
    sys.exit(main())
