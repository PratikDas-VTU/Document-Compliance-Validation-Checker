"""
run.py — Top-level launcher. Run this from the CA2/ directory:
    python run.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import main

if __name__ == "__main__":
    main()
