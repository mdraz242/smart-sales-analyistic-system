import sys
from pathlib import Path

# Add project root directory to sys.path so 'backend' is always importable
ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
