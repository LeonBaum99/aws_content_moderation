import os
import sys
import subprocess

def main():
    review_dir = "./devset_data"
    default_count = 9

    # Handle argument
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    files = sorted(
        [f for f in os.listdir(review_dir) if f.endswith('.json')]
    )

    if not files:
        print("No files found in", review_dir)
        return

    if arg is None:
        # Default: first 9 files
        to_process = files[:default_count]
    elif arg == "all":
        to_process = files
    else:
        try:
            count = int(arg)
            to_process = files[:count]
        except ValueError:
            print(f"Invalid argument: {arg} (must be integer or 'all')")
            return

    print(f"Processing {len(to_process)} file(s)...")

    for fname in to_process:
        local_path = os.path.join(review_dir, fname)
        s3_path = f"s3://reviews-input/{fname}"
        cmd = ["awslocal", "s3", "cp", local_path, s3_path]
        print("Running:", " ".join(cmd))
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error uploading {fname}: {e}")

if __name__ == "__main__":
    main()
