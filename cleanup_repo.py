#!/usr/bin/env python3
"""
Cleanup script to remove accidentally committed files from the repository
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(command, description):
    """Run a git command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return result.stdout
        else:
            print(f"❌ {description} failed: {result.stderr}")
            return None
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return None

def cleanup_repository():
    """Clean up the repository by removing accidentally committed files"""
    print("🧹 Repository Cleanup Script")
    print("=" * 50)
    
    # Check if we're in a git repository
    if not os.path.exists('.git'):
        print("❌ Not in a git repository. Please run this script from the repository root.")
        return False
    
    # Files and directories to remove from git tracking
    files_to_remove = [
        'Scrape/',
        'venv/',
        'env/',
        '.venv/',
        '__pycache__/',
        '*.pyc',
        '*.pyo',
        '*.pyd',
        '.pytest_cache/',
        'test-results/',
        'playwright-report/',
        'scraper.log',
        'test_results.json',
        'scraping_results.json'
    ]
    
    print("📋 Files/directories to remove from git tracking:")
    for file in files_to_remove:
        print(f"   - {file}")
    print()
    
    # Remove files from git tracking (but keep them locally)
    for file in files_to_remove:
        if os.path.exists(file) or file.endswith('*'):
            run_command(f'git rm -r --cached "{file}"', f"Removing {file} from git tracking")
    
    # Add the updated .gitignore
    run_command('git add .gitignore', "Adding updated .gitignore")
    
    # Commit the changes
    commit_message = "chore: remove accidentally committed files and update .gitignore"
    run_command(f'git commit -m "{commit_message}"', "Committing cleanup changes")
    
    print("\n🎉 Cleanup completed!")
    print("\n📝 Next steps:")
    print("1. Push the changes: git push")
    print("2. The files are now ignored and won't be committed again")
    print("3. Your local files are still there, just not tracked by git")
    
    return True

def show_status():
    """Show current git status"""
    print("\n📊 Current git status:")
    run_command('git status', "Checking git status")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--status':
        show_status()
    else:
        cleanup_repository()
