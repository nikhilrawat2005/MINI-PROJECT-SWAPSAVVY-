#!/usr/bin/env python3
"""
Clean up virtual environment and cache files
"""
import os
import shutil
import glob

def clean_project():
    """Remove virtual environment and cache files"""
    
    # Directories to remove
    dirs_to_remove = [
        'static/css/venv',
        'venv',
        '__pycache__',
        'app/__pycache__',
        'app/routes/__pycache__',
        'app/services/__pycache__',
        'migrations/__pycache__'
    ]
    
    # File patterns to remove
    file_patterns = [
        '*.pyc',
        'app/*.pyc',
        'app/routes/*.pyc',
        'app/services/*.pyc',
        'migrations/*.pyc'
    ]
    
    print("🧹 Cleaning project...")
    
    # Remove directories
    for dir_path in dirs_to_remove:
        if os.path.exists(dir_path):
            print(f"Removing directory: {dir_path}")
            shutil.rmtree(dir_path)
    
    # Remove files
    for pattern in file_patterns:
        for file_path in glob.glob(pattern):
            print(f"Removing file: {file_path}")
            os.remove(file_path)
    
    print("✅ Project cleaned successfully!")

if __name__ == '__main__':
    clean_project()