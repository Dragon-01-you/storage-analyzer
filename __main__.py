"""Entry point for the zipapp bundle.

`python storage-analyzer.pyz [args]` lands here.

We replicate the CLI surface of `engine.main.main()` but route through
this module so a zipapp (which expects __main__.py at the root) can
launch it without importing the project tree.
"""
import os
import sys

# zipapp bundles /engine and /cleaners as siblings, but Python looks
# for them on sys.path. Add the archive's own directory.
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def main():
    # Re-export engine.main.main()
    from engine.main import main as _main
    _main()


if __name__ == "__main__":
    main()
