#!/usr/bin/env python3
import subprocess
import sys
import os
import time
import shutil
import json

LOCAL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "laundering"
)

PRELOAD_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "preload"
)

MANIFEST_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "transferred_manifest.json"
)

REMOTE_DIR = "/storage/emulated/0/DCIM/Camera"

# keep some free space on device
SAFETY_BUFFER_BYTES = 0.5 * 1024 * 1024 * 1024  # 0.5 GB

# change this with debug coordinates if profile icon tap misses
PROFILE_TAP_X1 = 1005
PROFILE_TAP_Y1 = 133

PROFILE_TAP_X2 = 270
PROFILE_TAP_Y2 = 1190


def run(cmd):
    print(f"> {cmd}")

    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        print("Command failed. Exiting.")
        sys.exit(1)


def push_file(local_path, remote_dir, retries=3):
    filename = os.path.basename(local_path)

    for attempt in range(1, retries + 1):
        print(f"> Pushing {filename} (attempt {attempt})")

        result = subprocess.run(
            f'adb push "{local_path}" "{remote_dir}/"',
            shell=True
        )

        if result.returncode == 0:
            print(f"✔ Success: {filename}")
            return True

        print(f"⚠️ Failed: {filename}")

        if attempt < retries:
            print("Retrying in 2 seconds...")
            time.sleep(2)
        else:
            print(f"❌ Giving up on {filename}")
            return False


def get_free_space_bytes():
    result = subprocess.check_output(
        'adb shell "df /storage/emulated/0"',
        shell=True
    ).decode()

    lines = result.strip().splitlines()

    if len(lines) < 2:
        print("Could not determine free storage.")
        sys.exit(1)

    parts = lines[1].split()

    available_kb = int(parts[3])

    return available_kb * 1024


def save_manifest(files):
    with open(MANIFEST_FILE, "w") as f:
        json.dump(files, f, indent=2)


def load_manifest():
    if not os.path.exists(MANIFEST_FILE):
        return []

    with open(MANIFEST_FILE, "r") as f:
        return json.load(f)


def clear_manifest():
    if os.path.exists(MANIFEST_FILE):
        os.remove(MANIFEST_FILE)


def cleanup_transferred_files():
    transferred_files = load_manifest()

    if not transferred_files:
        print("No manifest found.")
        sys.exit(0)

    print("\nCleanup mode enabled.")
    print(f"Found {len(transferred_files)} transferred files.")

    confirm = input(
        "\nType DELETE to remove transferred files: "
    ).strip()

    if confirm != "DELETE":
        print("Aborted.")
        sys.exit(0)

    # delete from phone
    for filename in transferred_files:
        run(
            f'adb shell \'rm -f -- "{REMOTE_DIR}/{filename}"\''
        )

    # delete local copies
    for filename in transferred_files:
        local_path = os.path.join(LOCAL_DIR, filename)

        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"> rm {local_path}")

    clear_manifest()

    run("adb reboot")

    print("\n✅ Cleanup complete.")
    sys.exit(0)


def main():
    cleanup_mode = "--cleanup" in sys.argv

    if cleanup_mode:
        cleanup_transferred_files()

    # 1. check adb
    run("adb version")

    # 2. get local files
    try:
        files = [
            f for f in os.listdir(LOCAL_DIR)
            if os.path.isfile(os.path.join(LOCAL_DIR, f))
        ]
    except FileNotFoundError:
        print("Local laundering folder not found.")
        sys.exit(1)

    if not files:
        print("No files found in laundering folder.")
        sys.exit(0)

    # create preload folder
    os.makedirs(PRELOAD_DIR, exist_ok=True)

    # already transferred
    already_done = set(load_manifest())

    # 3. get total size
    total_bytes = sum(
        os.path.getsize(os.path.join(LOCAL_DIR, f))
        for f in files
    )

    total_mb = total_bytes / (1024 * 1024)

    if total_mb >= 1024:
        print(f"\nFound {len(files)} files (~{total_mb/1024:.2f} GB)")
    else:
        print(f"\nFound {len(files)} files (~{total_mb:.2f} MB)")

    # 4. get phone free space
    free_bytes = get_free_space_bytes()

    usable_bytes = max(
        0,
        free_bytes - SAFETY_BUFFER_BYTES
    )

    print(
        f"\nPhone free space: "
        f"{free_bytes / (1024**3):.2f} GB"
    )

    print(
        f"Usable transfer space: "
        f"{usable_bytes / (1024**3):.2f} GB\n"
    )

    # sort smallest first
    files_sorted = sorted(
        files,
        key=lambda f: os.path.getsize(
            os.path.join(LOCAL_DIR, f)
        )
    )

    print("\nStarting file transfers...\n")

    failed_files = []
    transferred_files = load_manifest()
    preloaded_files = []

    used_bytes = 0

    for filename in files_sorted:
        local_path = os.path.join(LOCAL_DIR, filename)

        # skip already transferred files
        if filename in already_done:
            print(f"⏩ Skipping already transferred: {filename}")
            transferred_files.append(filename)
            continue

        file_size = os.path.getsize(local_path)

        # doesn't fit
        if used_bytes + file_size > usable_bytes:
            preload_path = os.path.join(
                PRELOAD_DIR,
                filename
            )

            shutil.move(local_path, preload_path)

            preloaded_files.append(filename)

            print(f"📦 Moved to preload: {filename}")

            continue

        success = push_file(local_path, REMOTE_DIR)

        if success:
            transferred_files.append(filename)

            # save immediately so crashes are recoverable
            save_manifest(transferred_files)

            used_bytes += file_size
        else:
            failed_files.append(filename)

    # summary
    print("\nTransfer complete.")

    if failed_files:
        print("\n⚠️ Some files failed:")
        for f in failed_files:
            print(f" - {f}")
    else:
        print("\n✅ All transfers completed successfully.")

    if preloaded_files:
        print("\n📦 Deferred to preload folder:")
        for f in preloaded_files:
            print(f" - {f}")

    # 5. reboot device
    run("adb reboot")

    # 6. wait for device
    print("\nWaiting for device...")

    run("adb wait-for-device")

    time.sleep(7.5)

    print("the program is working dw")

    time.sleep(5.5)

    # wake swipe
    run("adb shell input swipe 500 1500 500 500")

    time.sleep(2.5)

    # 7. open Google Photos
    run(
        "adb shell am start "
        "-n com.google.android.apps.photos/.home.HomeActivity"
    )

    time.sleep(4)

    # 8. tap profile icon
    run(
        f"adb shell input tap "
        f"{PROFILE_TAP_X1} {PROFILE_TAP_Y1}"
    )

    time.sleep(2)

    run(
        f"adb shell input tap "
        f"{PROFILE_TAP_X2} {PROFILE_TAP_Y2}"
    )

    print("\nGoogle Photos opened.")
    print("WAIT for Google Photos to finish backing up.")
    print("When you are 100% sure, type DELETE to proceed:")

    confirm = input("> ").strip()

    if confirm != "DELETE" and confirm != "delete":

        print("Last try...")

        skibidi = input("> ").strip()

        if skibidi != "DELETE" and confirm != "delete":
            print("Aborted. Nothing deleted.")
            sys.exit(0)

    # 9. delete transferred files from phone
    for filename in transferred_files:
        run(
            f'adb shell \'rm -f -- "{REMOTE_DIR}/{filename}"\''
        )
        
        local_path = os.path.join(LOCAL_DIR, filename)

        if os.path.exists(local_path):
            os.remove(local_path)
            print(f"> rm {local_path}")

    # 10. delete transferred files from Mac
   # for filename in transferred_files:
   #     local_path = os.path.join(LOCAL_DIR, filename)
#
 #       if os.path.exists(local_path):
  #          os.remove(local_path)
   #         print(f"> rm {local_path}")

    # clear manifest after successful cleanup
    clear_manifest()

    # 11. final summary
    transferred_mb = used_bytes / (1024 * 1024)

    if transferred_mb >= 1024:
        print(
            f"\n✅ Freed "
            f"~{transferred_mb/1024:.2f} GB"
        )
    else:
        print(
            f"\n✅ Freed "
            f"~{transferred_mb:.2f} MB"
        )

    # reboot again for media rescan
    run("adb reboot")


if __name__ == "__main__":
    main()

# normal run:
# python3 script.py

# cleanup-only mode:
# python3 script.py --cleanup

# cleanup-only mode:
# python3 PixelHopping.py --cleanup

# remove duplicates:
# rm -f ~/Desktop/laundering/*\ 2.*