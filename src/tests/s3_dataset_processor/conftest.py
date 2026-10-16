"""Make the processor importable: it imports its neighbours (constants, services) by plain name."""

import sys
from pathlib import Path

PROCESSOR_DIR = Path(__file__).resolve().parents[2] / "s3_dataset_processor"
sys.path.insert(0, str(PROCESSOR_DIR))
