"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Verify Hardcoded Paths
"""

"""Script to verify no hardcoded paths remain in the codebase."""
import os
import re

# Patterns to search for (excluding comments and docstrings)
patterns = [
    r'D:/Predict',
    r'D:\\Predict',
    r'C:/OBDserver',
    r'C:\\OBDserver',
]

def is_code_line(line):
    """Check if line is actual code, not a comment or docstring."""
    stripped = line.strip()
    # Skip empty lines
    if not stripped:
        return False
    # Skip comments
    if stripped.startswith('#'):
        return False
    # Skip docstring markers
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return False
    # Skip lines that are just strings (likely in docstrings)
    if stripped.startswith('"') or stripped.startswith("'"):
        # But allow strings with assignments
        if '=' in stripped and not stripped.startswith(('"""', "'''")):
            return True
        return False
    return True

def search_for_hardcoded_paths():
    """Search for hardcoded paths in Python files."""
    matches = []
    
    for root, dirs, files in os.walk('.'):
        # Skip .git and other hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for filename in files:
            if filename.endswith('.py'):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    for i, line in enumerate(lines, 1):
                        if not is_code_line(line):
                            continue
                        
                        for pattern in patterns:
                            if re.search(pattern, line):
                                matches.append((filepath, i, line.strip()))
                                break
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return matches

if __name__ == '__main__':
    matches = search_for_hardcoded_paths()
    
    if matches:
        print(f"Found {len(matches)} hardcoded path(s):\n")
        for filepath, line_num, line in matches:
            print(f"{filepath}:{line_num}")
            print(f"  {line}\n")
    else:
        print("✓ No hardcoded paths found in code!")
