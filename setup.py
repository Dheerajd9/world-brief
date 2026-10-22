"""Setup wizard: python setup.py  (writes config.yaml; prints or saves your keys)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
import setup_wizard  # noqa: E402

if __name__ == "__main__":
    sys.exit(setup_wizard.main())
