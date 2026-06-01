"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Copyright Header Automation Script
"""

import os
import sys
from pathlib import Path
from typing import List, Dict

# Copyright header templates
PYTHON_HEADER = '''"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: {module_name}
"""

'''

KOTLIN_HEADER = '''/*
 * PREDICT - Vehicle Intelligence Platform
 * Copyright © 2026 PREDICT
 * All rights reserved.
 *
 * This file is proprietary and confidential.
 * Unauthorized copying, modification, distribution, or use is strictly prohibited.
 *
 * Created: January 2026
 * Module: {module_name}
 */

'''

XML_HEADER = '''<!--
  PREDICT - Vehicle Intelligence Platform
  Copyright © 2026 PREDICT
  All rights reserved.

  This file is proprietary and confidential.
  Unauthorized copying, modification, distribution, or use is strictly prohibited.
-->

'''


def has_copyright(content: str) -> bool:
    """Check if file already has copyright notice."""
    return "Copyright © 2026 PREDICT" in content


def get_module_name(file_path: Path) -> str:
    """Generate module name from file path."""
    return file_path.stem.replace('_', ' ').title()


def add_python_header(file_path: Path) -> bool:
    """Add copyright header to Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if has_copyright(content):
            print(f"  [SKIP] Already has copyright: {file_path.name}")
            return False

        module_name = get_module_name(file_path)
        header = PYTHON_HEADER.format(module_name=module_name)

        # Handle different file starts
        if content.startswith('"""') or content.startswith("'''"):
            # Find end of existing docstring
            quote = '"""' if content.startswith('"""') else "'''"
            end_idx = content.find(quote, 3)
            if end_idx != -1:
                # Preserve original docstring content in header
                original_doc = content[3:end_idx].strip()
                header = f'''"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: {module_name}

{original_doc}
"""

'''
                content = header + content[end_idx+3:].lstrip()
            else:
                content = header + content
        elif content.startswith('#'):
            # Comment at top - replace it
            lines = content.split('\n')
            first_code_line = 0
            for i, line in enumerate(lines):
                if line.strip() and not line.strip().startswith('#'):
                    first_code_line = i
                    break
            content = header + '\n'.join(lines[first_code_line:])
        else:
            # Just prepend
            content = header + content

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  [OK] Added copyright: {file_path.name}")
        return True

    except Exception as e:
        print(f"  [ERROR] {file_path.name}: {str(e)}")
        return False


def add_kotlin_header(file_path: Path) -> bool:
    """Add copyright header to Kotlin file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if has_copyright(content):
            print(f"  [SKIP] Already has copyright: {file_path.name}")
            return False

        module_name = get_module_name(file_path)
        header = KOTLIN_HEADER.format(module_name=module_name)

        # Kotlin files start with package declaration
        if content.startswith('package '):
            content = header + content
        else:
            content = header + content

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  [OK] Added copyright: {file_path.name}")
        return True

    except Exception as e:
        print(f"  [ERROR] {file_path.name}: {str(e)}")
        return False


def add_xml_header(file_path: Path) -> bool:
    """Add copyright header to XML file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if has_copyright(content):
            print(f"  [SKIP] Already has copyright: {file_path.name}")
            return False

        # XML files start with <?xml ... ?>
        if content.startswith('<?xml'):
            xml_decl_end = content.find('?>') + 2
            content = content[:xml_decl_end] + '\n' + XML_HEADER + content[xml_decl_end:]
        else:
            content = XML_HEADER + content

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  [OK] Added copyright: {file_path.name}")
        return True

    except Exception as e:
        print(f"  [ERROR] {file_path.name}: {str(e)}")
        return False


def process_directory(directory: Path, file_extension: str, handler_func) -> Dict[str, int]:
    """Process all files with given extension in directory."""
    stats = {'added': 0, 'skipped': 0, 'errors': 0}

    if not directory.exists():
        print(f"  [WARNING] Directory does not exist: {directory}")
        return stats

    files = list(directory.rglob(f"*{file_extension}"))
    print(f"\n  Found {len(files)} {file_extension} files in {directory}")

    for file_path in files:
        # Skip build/generated directories
        if any(skip in str(file_path) for skip in ['build', 'generated', '.gradle', '.idea', '__pycache__', 'venv', 'node_modules']):
            continue

        result = handler_func(file_path)
        if result:
            stats['added'] += 1
        elif has_copyright(open(file_path, 'r', encoding='utf-8').read()):
            stats['skipped'] += 1
        else:
            stats['errors'] += 1

    return stats


def main():
    """Main function to add copyright headers to all projects."""
    print("="*70)
    print("PREDICT Copyright Header Automation")
    print("="*70)

    # Define project directories
    projects = {
        'Desktop App (Python)': {
            'path': Path(r'c:\D Drive\Predict'),
            'extension': '.py',
            'handler': add_python_header
        },
        'Previlium OBD Server (Python)': {
            'path': Path(r'c:\D Drive\Predict\Previlium_OBD_Server'),
            'extension': '.py',
            'handler': add_python_header
        },
        'PredictOBD Android App (Kotlin)': {
            'path': Path(r'C:\Predict\PredictOBD\app\src\main\java'),
            'extension': '.kt',
            'handler': add_kotlin_header
        },
        'PredictOBD Android XML': {
            'path': Path(r'C:\Predict\PredictOBD\app\src\main\res'),
            'extension': '.xml',
            'handler': add_xml_header
        },
        'Guardian Android App (Kotlin)': {
            'path': Path(r'C:\Predict guardian\app\src\main\java'),
            'extension': '.kt',
            'handler': add_kotlin_header
        },
        'Guardian Android XML': {
            'path': Path(r'C:\Predict guardian\app\src\main\res'),
            'extension': '.xml',
            'handler': add_xml_header
        }
    }

    total_stats = {'added': 0, 'skipped': 0, 'errors': 0}

    for project_name, config in projects.items():
        print(f"\n{'='*70}")
        print(f"Processing: {project_name}")
        print(f"{'='*70}")

        stats = process_directory(
            config['path'],
            config['extension'],
            config['handler']
        )

        print(f"\n  Results:")
        print(f"    Added:   {stats['added']}")
        print(f"    Skipped: {stats['skipped']}")
        print(f"    Errors:  {stats['errors']}")

        total_stats['added'] += stats['added']
        total_stats['skipped'] += stats['skipped']
        total_stats['errors'] += stats['errors']

    print(f"\n{'='*70}")
    print(f"TOTAL SUMMARY")
    print(f"{'='*70}")
    print(f"  Total files processed:      {total_stats['added'] + total_stats['skipped']}")
    print(f"  Copyright headers added:    {total_stats['added']}")
    print(f"  Already had copyright:      {total_stats['skipped']}")
    print(f"  Errors:                     {total_stats['errors']}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
