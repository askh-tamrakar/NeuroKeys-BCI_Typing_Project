"""
🔧 AUTOMATIC WINDOWS EMOJI FIX
Adds UTF-8 encoding fix to all Python files in one go
"""

import os
import sys
from pathlib import Path

def add_encoding_fix(filepath):
    """Add UTF-8 encoding fix to a Python file"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if fix already applied
    if "sys.stdout.reconfigure(encoding='utf-8')" in content:
        print(f"✓ Already fixed: {filepath}")
        return True
    
    lines = content.split('\n')
    
    # Find where to insert the fix (after shebang and docstring)
    insert_pos = 0
    in_docstring = False
    docstring_char = None
    
    for i, line in enumerate(lines):
        # Skip shebang
        if i == 0 and line.startswith('#!'):
            insert_pos = i + 1
            continue
        
        # Skip module docstring
        if '"""' in line or "'''" in line:
            if not in_docstring:
                in_docstring = True
                docstring_char = line[:line.index('"' if '"' in line else "'")]
            else:
                in_docstring = False
            continue
        
        # After docstring, find imports
        if not in_docstring and (line.startswith('import ') or line.startswith('from ')):
            # Found imports section
            insert_pos = i
            break
    
    # Find the sys import
    sys_import_line = None
    for i in range(insert_pos, len(lines)):
        if 'import sys' in lines[i]:
            sys_import_line = i
            break
    
    if sys_import_line is None:
        # No sys import found, add it
        sys_import_line = insert_pos
        lines.insert(insert_pos, 'import sys')
    
    # Add the encoding fix right after sys import
    fix_line = "sys.stdout.reconfigure(encoding='utf-8')  # Windows emoji fix"
    
    # Check if the next line is already the fix
    if sys_import_line + 1 < len(lines) and fix_line in lines[sys_import_line + 1]:
        print(f"✓ Already has fix: {filepath}")
        return True
    
    lines.insert(sys_import_line + 1, fix_line)
    
    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ Fixed: {filepath}")
    return True

def main():
    """Auto-fix all Python files"""
    
    print("=" * 60)
    print("🔧 WINDOWS EMOJI FIX - Auto Patcher")
    print("=" * 60)
    print()
    
    files_to_fix = [
        'websocket_bridge.py',
        'api_server.py',
        'launcher.py',
        'unified_acquisition.py',
        'data_router.py'
    ]
    
    project_root = Path(__file__).parent
    fixed_count = 0
    
    for filename in files_to_fix:
        filepath = project_root / "src/acquisition" / filename
        
        if filepath.exists():
            try:
                if add_encoding_fix(filepath):
                    fixed_count += 1
            except Exception as e:
                print(f"❌ Error fixing {filename}: {e}")
        else:
            print(f"⚠️  Not found: {filename}")
    
    print()
    print("=" * 60)
    print(f"✅ Fixed {fixed_count} files!")
    print()
    print("All Python files now have UTF-8 emoji support on Windows.")
    print("You can now run: python launcher.py --with-frontend")
    print("=" * 60)

if __name__ == '__main__':
    main()
