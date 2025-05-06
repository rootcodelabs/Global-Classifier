#!/bin/bash

# Variables
folder_path="DSL/Liquibase/changelog"
liquibase_folder="DSL/Liquibase"
user_input_name="$1"  # User input for the name (e.g., user-given name)
file_extension="$2"  # User input for the file extension (e.g., "sql" or "xml")

# Function to increment version
increment_version() {
    local version=$1
    local prefix=$(echo "$version" | grep -oP '\d+')
    local new_version=$((prefix + 1))
    echo "v${new_version}"
}

# Find the file with the highest version number matching the format classifier-script-vXX.*
max_version_file=$(ls "$folder_path"/classifier-script-v*.* 2>/dev/null | grep -oP "$folder_path/classifier-script-v\d+" | sort -t 'v' -k 2,2 -n | tail -n 1)

if [[ -z "$max_version_file" ]]; then
    # No files found, start with version v1
    current_version="v0"
else
    # Extract the current version
    current_version=$(echo "$max_version_file" | grep -oP 'v\d+')
fi

# Increment the version
new_version=$(increment_version "$current_version")

# Form new file name with the incremented version and user input name
new_file="classifier-script-${new_version}-${user_input_name}.${file_extension}"

# Create the new file with the appropriate header
if [ "$file_extension" = "sql" ]; then
    echo "-- liquibase formatted sql" > "$folder_path/$new_file"
elif [ "$file_extension" = "xml" ]; then
    echo '<?xml version="1.0" encoding="UTF-8"?>' > "$folder_path/$new_file"
else
    echo "Unsupported file extension."
    exit 1
fi

echo "Created new file: $new_file with header"

# Path to the master.yml file in the Liquibase folder
master_yml_file="$liquibase_folder/master.yml"

# Add entry to Liquibase master.yml
echo "  - include:" >> "$master_yml_file"
echo "      file: changelog/$new_file" >> "$master_yml_file"
echo "Updated $master_yml_file with file: changelog/$new_file"

git add "$folder_path/$new_file"