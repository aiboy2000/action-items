#!/usr/bin/env python3
import sys
import unittest
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Discover and run tests
loader = unittest.TestLoader()
start_dir = 'tests'
suite = loader.discover(start_dir, pattern='test_*.py')

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Exit with proper code
sys.exit(0 if result.wasSuccessful() else 1)