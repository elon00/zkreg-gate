"""Compatibility entrypoint: run real offline tests, never claim ZK verification."""
import subprocess
import sys

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]))
