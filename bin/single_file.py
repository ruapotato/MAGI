#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def should_exclude(path):
    """Check if the path should be excluded based on criteria."""
    excluded_dirs = {'magi-os-build'}
    
    # Check for *_pyenv pattern anywhere in the path
    if any(part.endswith('_pyenv') for part in path.parts):
        return True
    
    # Check each part of the path against excluded directories
    return any(excluded_dir in path.parts for excluded_dir in excluded_dirs)

def find_files(directory, extensions):
    """Recursively find all files with given extensions in directory."""
    files = []
    for ext in extensions:
        for file_path in Path(directory).rglob(f'*.{ext}'):
            if not should_exclude(file_path):
                files.append(file_path)
    return sorted(files)

def read_file_content(file_path):
    """Read and return the content of a file with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"

def format_file_content(file_path, content):
    """Format file content with header."""
    separator = "=" * 80
    return f"\n{separator}\n{file_path}\n{separator}\n{content}\n"

def ensure_directory_exists(path):
    """Create directory if it doesn't exist."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)

def main():
    # Get project root directory (parent of bin directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Setup output path
    output_path = Path('/tmp/magi_realm/project_context.txt')
    ensure_directory_exists(output_path)
    
    # Find all .sh and .py files
    files = find_files(project_root, ['sh', 'py'])
    
    # Print just filenames to stdout
    print("Found files:")
    for file_path in files:
        relative_path = file_path.relative_to(project_root)
        print(relative_path)
    
    # Write detailed output to file
    output_content = "Project Files Dump\n\n"
    for file_path in files:
        relative_path = file_path.relative_to(project_root)
        content = read_file_content(file_path)
        output_content += format_file_content(relative_path, content)
    
    # Write to file
    try:
        output_path.write_text(output_content, encoding='utf-8')
        print(f"\nFull content written to {output_path}", file=sys.stderr)
        print(f"Size: {len(output_content):,} bytes", file=sys.stderr)
    except Exception as e:
        print(f"\nError writing to file: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    main()
