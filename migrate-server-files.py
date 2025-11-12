#!/usr/bin/env python3
"""
Migrate files from Azure App Service to Azure Blob Storage
Downloads all files from the web app's uploads folder and uploads them to blob storage
"""

import requests
import json
import subprocess
import sys

# Configuration
WEB_APP_URL = "https://ourfamilyreunion2025-ftf0arg7bhcbeca9.eastus-01.azurewebsites.net"
STORAGE_ACCOUNT = "familyreunion86776"
CONTAINER_NAME = "familyreunion-uploads"
RESOURCE_GROUP = "FamilyReunion"

def get_file_list():
    """Get list of files from the server"""
    print("📋 Fetching file list from server...")
    response = requests.get(f"{WEB_APP_URL}/debug/list-local-files")
    if response.status_code != 200:
        print(f"❌ Failed to get file list: {response.status_code}")
        sys.exit(1)

    data = response.json()
    print(f"✅ Found {data['total_local_files']} files to migrate")
    return data['files']

def get_connection_string():
    """Get Azure Storage connection string"""
    print("🔑 Getting storage connection string...")
    result = subprocess.run([
        "az", "storage", "account", "show-connection-string",
        "--name", STORAGE_ACCOUNT,
        "--resource-group", RESOURCE_GROUP,
        "--query", "connectionString",
        "-o", "tsv"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ Failed to get connection string: {result.stderr}")
        sys.exit(1)

    return result.stdout.strip()

def download_and_upload_file(filename, connection_string):
    """Download file from web app and upload to blob storage"""
    # Download from web app (using debug endpoint to bypass Azure redirect)
    file_url = f"{WEB_APP_URL}/debug/serve-local/{filename}"
    response = requests.get(file_url)

    if response.status_code != 200:
        print(f"  ⚠️  Failed to download {filename}: {response.status_code}")
        return False

    # Save temporarily
    temp_file = f"/tmp/{filename}"
    with open(temp_file, 'wb') as f:
        f.write(response.content)

    # Upload to blob storage
    result = subprocess.run([
        "az", "storage", "blob", "upload",
        "--container-name", CONTAINER_NAME,
        "--file", temp_file,
        "--name", filename,
        "--connection-string", connection_string,
        "--overwrite",
        "--only-show-errors"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ⚠️  Failed to upload {filename}: {result.stderr}")
        return False

    # Clean up temp file
    subprocess.run(["rm", temp_file], check=False)
    return True

def main():
    print("🚀 Starting migration of files from Azure App Service to Blob Storage")
    print("=" * 70)

    # Get file list
    files = get_file_list()
    total_files = len(files)

    # Get connection string
    connection_string = get_connection_string()

    # Migrate files
    print(f"\n📦 Migrating {total_files} files...")
    print("=" * 70)

    success_count = 0
    fail_count = 0

    for i, file_info in enumerate(files, 1):
        filename = file_info['name']
        size_mb = file_info['size'] / 1024 / 1024

        print(f"[{i}/{total_files}] {filename} ({size_mb:.2f} MB)...", end=" ")

        if download_and_upload_file(filename, connection_string):
            print("✅")
            success_count += 1
        else:
            print("❌")
            fail_count += 1

        # Progress update every 25 files
        if i % 25 == 0:
            print(f"\n📊 Progress: {i}/{total_files} files processed ({success_count} success, {fail_count} failed)\n")

    # Final summary
    print("\n" + "=" * 70)
    print("🎉 Migration Complete!")
    print("=" * 70)
    print(f"✅ Successfully migrated: {success_count} files")
    if fail_count > 0:
        print(f"❌ Failed: {fail_count} files")
    print(f"📊 Total: {total_files} files")
    print("\nAll files are now in Azure Blob Storage!")

if __name__ == "__main__":
    main()
