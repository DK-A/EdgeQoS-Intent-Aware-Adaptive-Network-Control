#!/usr/bin/env python3
"""
ml/compare_baseline.py - Rigorous Comparison: TinyML Decision Tree vs. Deterministic Rule Baseline
Evaluates both classifiers on the held-out real-stack test partition (ml-v2 protocol).
Delegates directly to ml/evaluate.py to ensure complete scientific consistency.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ml.evaluate import main

if __name__ == "__main__":
    main()
