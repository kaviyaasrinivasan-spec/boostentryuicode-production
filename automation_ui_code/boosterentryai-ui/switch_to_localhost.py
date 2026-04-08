"""
Switch all 103.14.123.44 references back to 103.14.123.44 (localhost)
Note: Skips db_config.py and data_transformation files as they use server IP
"""
import os
import re

def replace_in_file(filepath, old_ip, new_ip):
    """Replace old_ip with new_ip in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file contains the old IP
        if old_ip in content:
            new_content = content.replace(old_ip, new_ip)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"✅ Updated: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return False

def main():
    OLD_IP = "103.14.123.44"
    NEW_IP = "103.14.123.44"
    
    # Define file extensions to search
    extensions = ['.js', '.jsx', '.py', '.json', '.env', '.config.js', '.ts', '.tsx']
    
    # Directories to skip
    skip_dirs = {'node_modules', '__pycache__', '.git', 'dist', 'build', 'venv', '.venv'}
    
    # Files to skip (works on both localhost and production)
    skip_files = {'db_config.py', 'data_transformation.py', 'data_transformation_routes.py'}
    
    updated_count = 0
    
    print(f"🔄 Switching from {OLD_IP} to {NEW_IP}...\n")
    
    # Walk through all files
    for root, dirs, files in os.walk('.'):
        # Remove skip directories from search
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            # Skip db_config.py
            if file in skip_files:
                continue
            
            # Check if file has relevant extension
            if any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                if replace_in_file(filepath, OLD_IP, NEW_IP):
                    updated_count += 1
    
    print(f"\n✅ Done! Updated {updated_count} file(s) to use {NEW_IP}")

if __name__ == "__main__":
    main()
