"""Make the processor importable: it imports its neighbours (constants, services) by plain name."""

import os
import sys
from pathlib import Path

PROCESSOR_DIR = Path(__file__).resolve().parents[2] / "s3_dataset_processor"
sys.path.insert(0, str(PROCESSOR_DIR))

# constants.py reads service URLs from constants.ini, which lives at /app in the container
os.environ.setdefault(
    "CONSTANTS_FILE", str(Path(__file__).resolve().parents[3] / "constants.ini")
)
