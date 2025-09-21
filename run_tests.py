#!/usr/bin/env python3
"""Test runner script for bank statement processor."""

import sys
import subprocess
from pathlib import Path

def run_tests():
    """Run the test suite with appropriate options."""
    project_root = Path(__file__).parent
    
    # Basic test command
    cmd = [
        sys.executable, '-m', 'pytest',
        str(project_root / 'tests'),
        '-v',
        '--tb=short'
    ]
    
    print("🧪 Running Bank Statement Processor Tests")
    print("=" * 50)
    
    try:
        result = subprocess.run(cmd, cwd=project_root)
        return result.returncode
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

if __name__ == '__main__':
    exit_code = run_tests()
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {exit_code}")
    sys.exit(exit_code)