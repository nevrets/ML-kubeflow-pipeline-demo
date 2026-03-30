#!/bin/bash

# Define directories to process
DIRECTORIES="00-kubeflow-function 01-data-loading 02-model-training"
TARGET_REPO="${REGISTRY_HOST:-<REGISTRY_HOST>}/iris/demo"

# Function to build Docker image
build_podman_image() {
    local dir=$1
    local image_name=$2

    if [ -f "$dir/dockerfile" ] || [ -f "$dir/Dockerfile" ]; then
        echo "Building Docker image for $image_name from directory $dir"
        echo "$TARGET_REPO/$image_name:latest" "$dir"
        podman build --no-cache -t "$TARGET_REPO/$image_name:latest" "$dir"
        podman push "$TARGET_REPO/$image_name:latest"
    else
        echo "No Dockerfile found in $dir. Skipping..."
    fi
}

# Process each directory
for BASE_DIR in $DIRECTORIES; do
    echo "Processing directory: $BASE_DIR"
    
    # Skip if directory doesn't exist
    if [ ! -d "$BASE_DIR" ]; then
        echo "Directory $BASE_DIR not found. Skipping..."
        continue
    fi

    # First check if there's a Dockerfile in the base directory
    if [ -f "$BASE_DIR/dockerfile" ] || [ -f "$BASE_DIR/Dockerfile" ]; then
        echo "Found Dockerfile in base directory: $BASE_DIR"
        build_podman_image "$BASE_DIR" "$BASE_DIR"
    fi

    # Then check subdirectories if they exist
    if [ "$(ls -A $BASE_DIR)" ]; then
        for subdir in "$BASE_DIR"/*; do
            if [ -d "$subdir" ]; then
                parent_name=$(basename "$subdir")
                if [ -f "$subdir/dockerfile" ] || [ -f "$subdir/Dockerfile" ]; then
                    build_podman_image "$subdir" "$BASE_DIR/$parent_name"
                fi
            fi
        done
    fi
done

echo "Podman build process completed."