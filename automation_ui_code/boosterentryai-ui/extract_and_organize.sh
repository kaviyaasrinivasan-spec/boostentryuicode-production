#!/bin/bash

# ==========================================
# CONFIGURATION
# ==========================================
CONTAINER_NAME="boosterentryai-app"
# The path INSIDE the container where your code lives. 
# Common defaults: /app, /usr/src/app, or /code.
# Update this if your container stores code elsewhere.
CONTAINER_SOURCE_PATH="/app" 

HOST_BASE_DEST="/root/boostuicode"
TEMP_STAGING_DIR="/tmp/docker_code_staging"

# Destination subfolders
FRONTEND_DEST="$HOST_BASE_DEST/frontend"
BACKEND_DEST="$HOST_BASE_DEST/backend"
OTHERS_DEST="$HOST_BASE_DEST/others"

# Exclusions (passed to find command)
# We handle exclusions during the copy or the find step.
# It is faster to exclude heavily populated dirs like node_modules from the find loop.
EXCLUDES=(
    ".git"
    ".venv"
    "venv"
    "node_modules"
    "__pycache__"
    "uploaded_docs"
    "processed_docs"
)

# ==========================================
# EXECUTION
# ==========================================

echo "Step 1: Preparing directories..."
mkdir -p "$FRONTEND_DEST"
mkdir -p "$BACKEND_DEST"
mkdir -p "$OTHERS_DEST"
rm -rf "$TEMP_STAGING_DIR"
mkdir -p "$TEMP_STAGING_DIR"

echo "Step 2: Copying files from container '$CONTAINER_NAME'..."
echo "      Source: $CONTAINER_SOURCE_PATH"
echo "      Temp:   $TEMP_STAGING_DIR"

# Try to copy. If /app doesn't exist, this might fail.
if docker cp "$CONTAINER_NAME:$CONTAINER_SOURCE_PATH/." "$TEMP_STAGING_DIR"; then
    echo "✅ Copy successful."
else
    echo "❌ Failed to copy from docker. Check if '$CONTAINER_SOURCE_PATH' exists inside the container."
    exit 1
fi

echo "Step 3: Organizing files into $HOST_BASE_DEST..."

# Build find exclusion args
FIND_OPTS=""
for excl in "${EXCLUDES[@]}"; do
    FIND_OPTS="$FIND_OPTS -name $excl -prune -o"
done

# Process files
find "$TEMP_STAGING_DIR" $FIND_OPTS -type f -print | while read -r file; do
    # Get relative path from staging root
    # remove the staging dir prefix
    rel_path="${file#$TEMP_STAGING_DIR/}"
    
    # Clean up leading slash if present
    rel_path="${rel_path#/}"
    
    dir_path=$(dirname "$rel_path")
    filename=$(basename "$file")
    extension="${filename##*.}"
    
    # Determine target root
    if [[ "$extension" == "py" ]]; then
        TARGET_ROOT="$BACKEND_DEST"
    elif [[ "$extension" == "jsx" || "$extension" == "js" || "$extension" == "tsx" || "$extension" == "ts" || "$extension" == "css" ]]; then
        TARGET_ROOT="$FRONTEND_DEST"
    else
        TARGET_ROOT="$OTHERS_DEST"
    fi
    
    # Create target parent dir
    FULL_TARGET_DIR="$TARGET_ROOT/$dir_path"
    mkdir -p "$FULL_TARGET_DIR"
    
    # Move file (using cp to be safe, could be mv)
    cp "$file" "$FULL_TARGET_DIR/"
done

echo "Step 4: Cleanup..."
rm -rf "$TEMP_STAGING_DIR"

echo "============================================"
echo "Extraction & Organization Complete!"
echo "Backend:  $BACKEND_DEST"
echo "Frontend: $FRONTEND_DEST"
echo "Others:   $OTHERS_DEST"
echo "============================================"
