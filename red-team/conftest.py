"""
Pytest conftest.py — Red Team test suite
Sets PYTHONPATH and provides shared fixtures.
"""
import os
import sys

# Ensure project root is on sys.path so `app.*` and `ml.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
