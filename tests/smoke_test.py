"""Smoke test the built wheel or source distribution.

Run through uv after building, for example:

    uv run --isolated --no-project --with dist/*.whl tests/smoke_test.py

This checks that the installed distribution exposes the public API and CLI,
not just that the repository checkout works.
"""

from __future__ import annotations

from importlib.metadata import version

from image_workflow import import_images, sanitize_component
from image_workflow.cli import build_parser


def main() -> None:
    assert version("image-workflow")
    assert import_images is not None
    assert sanitize_component("Canon  Inc.") == "Canon-Inc."

    parser = build_parser()
    args = parser.parse_args(["import", "photos", "--dry-run"])
    assert args.command == "import"

    print("image-workflow smoke test passed")


if __name__ == "__main__":
    main()
