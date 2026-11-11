"""Django management entry point."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.server.bootstrap import manage  # noqa: E402

if __name__ == "__main__":
    manage(sys.argv[1:])
