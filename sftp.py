import os
import paramiko
from tqdm import tqdm
import re
from datetime import datetime

# ------------------- Config -------------------
HOST = "34.93.153.50"
PORT = 22
USERNAME = "bmpl"
PASSWORD = "BMPL@Nokia#05092025"

UPLOAD_PATHS = {
    "1": "/SCFT_Regeneration/MAH_MUM_ROB/4G/Bharti_4G",
    "2": "/SCFT_Regeneration/MAH_MUM_ROB/2G/Bharti_2G",
    "3": "/SCFT_Regionwide/MAH/5G/Bharti_5G_4"
}

DOWNLOAD_PATH = "/MAH/BMPL"
# ----------------------------------------------

def extract_timestamp_from_filename(filename):
    """Extract the timestamp from filenames like `20250909T173845Z`."""
    match = re.search(r'(\d{8}T\d{6}Z)', filename)
    if match:
        return datetime.strptime(match.group(0), "%Y%m%dT%H%M%SZ")
    return None

def get_all_files(local_dir):
    """Return a list of all files under local_dir (recursive)."""
    file_list = []
    for root, dirs, files in os.walk(local_dir):
        for f in files:
            file_list.append(os.path.join(root, f))
    return file_list

def sort_files_by_priority_and_timestamp(files):
    """Sort the files first by priority (txt files first) and then by timestamp."""
    txt_files = [f for f in files if f.lower().endswith('.txt')]
    non_txt_files = [f for f in files if not f.lower().endswith('.txt')]

    # Sort non-txt files by timestamp
    non_txt_files.sort(key=lambda f: extract_timestamp_from_filename(f), reverse=True)

    # Combine txt files first and then the sorted non-txt files
    return txt_files + non_txt_files

def upload_dir(sftp, local_dir, remote_dir, global_bar):
    """Recursively upload a local directory to a remote directory over SFTP."""
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass  # Directory may already exist

    all_files = get_all_files(local_dir)
    all_files_sorted = sort_files_by_priority_and_timestamp(all_files)

    for local_file in all_files_sorted:
        relative_path = os.path.relpath(local_file, local_dir)
        remote_file = os.path.join(remote_dir, relative_path).replace("\\", "/")
        upload_file(sftp, local_file, remote_file)
        global_bar.update(1)

def upload_file(sftp, local_file, remote_file):
    """Upload a single file with per-file progress tracking."""
    file_size = os.path.getsize(local_file)

    with tqdm(
        total=file_size,
        unit='B',
        unit_scale=True,
        desc=os.path.basename(local_file),
        leave=False
    ) as progress_bar:

        def callback(transferred, total):
            progress_bar.update(transferred - progress_bar.n)

        sftp.put(local_file, remote_file, callback=callback)

def main():
    while True:  # Loop to allow restarting
        # ---------- Connection ----------
        try:
            transport = paramiko.Transport((HOST, PORT))
            transport.connect(username=USERNAME, password=PASSWORD)
            sftp = paramiko.SFTPClient.from_transport(transport)
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return

        # ---------- User Selection ----------
        print("Select an option:")
        print("1. Upload 4G")
        print("2. Upload 2G")
        print("3. Upload 5G")
        print("4. Download Report")

        choice = input("Enter your choice (1-4): ").strip()

        # ---------- Upload ----------
        if choice in ["1", "2", "3"]:
            local_dir = input("Enter the local directory path to upload: ").strip()
            if not os.path.isdir(local_dir):
                print("Invalid directory.")
                return

            remote_path = UPLOAD_PATHS[choice]

            print(f"\nScanning: {local_dir}")
            all_files = get_all_files(local_dir)
            total_files = len(all_files)
            print(f"Found {total_files} files to upload.\n")

            with tqdm(total=total_files, unit="file", desc="Total Upload Progress") as global_bar:
                upload_dir(sftp, local_dir, remote_path, global_bar)

            print("Upload completed successfully!")

        # ---------- Download ----------
        elif choice == "4":
            search_id = input("Enter the ID to search in report filenames: ").strip()
            print(f"🔍 Searching for ID: {search_id} in remote reports...\n")

            try:
                # Only get .xlsx files that match the search term
                remote_files = [f for f in sftp.listdir(DOWNLOAD_PATH) if search_id in f and f.endswith('.xlsx')]
            except Exception as e:
                print(f"Error accessing report directory: {e}")
                return

            if not remote_files:
                print("No matching files found.")
                return

            # List the files
            for idx, file in enumerate(remote_files):
                print(f"[{idx}] {file}")

            # Ask user for file selection
            selected = input("\nEnter indexes to download (comma-separated): ").strip()
            indexes = []
            for part in selected.split(","):
                try:
                    indexes.append(int(part.strip()))
                except ValueError:
                    print(f"Skipping invalid index: {part}")

            local_dir = input("Enter the local directory to save downloaded files: ").strip()

            # Download selected files
            downloaded_files = download_files_by_indexes(sftp, remote_files, indexes, local_dir)

            # Display downloaded files and their local directory locations
            print("\nDownload completed.\n")
            print("Downloaded files:")
            for filename, local_file in downloaded_files:
                print(f"{filename} -> {local_file}")

            # Ask if the user wants to start from the beginning
            restart = input("\nDo you want to start from the first? (y/n): ").strip().lower()
            if restart != 'y':
                print("Exiting the program.")
                break

        else:
            print("Invalid selection. Please choose between 1 and 4.")

        sftp.close()
        transport.close()

if __name__ == "__main__":
    main()
