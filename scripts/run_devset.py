import os
import sys
import subprocess
import math

def main():
    review_dir = "./devset_data"
    default_count = 9

    # Handle argument
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    # Gather JSON files
    files = sorted([f for f in os.listdir(review_dir) if f.endswith('.json')])

    if not files:
        print("No files found in", review_dir)
        return

    # Determine which files to process
    if arg is None:
        to_process = files[:default_count]
    elif arg == "all":
        to_process = files
    elif arg == "10%":
        count = math.ceil(len(files) * 0.1)
        to_process = files[:count]
    else:
        try:
            count = int(arg)
            to_process = files[:count]
        except ValueError:
            print(f"Invalid argument: {arg} (must be integer or 'all')")
            return

    total = len(to_process)
    print(f"Processing {total} file(s)...")

    # Upload loop with progress
    for idx, fname in enumerate(to_process, start=1):
        local_path = os.path.join(review_dir, fname)
        s3_path = f"s3://reviews-input/{fname}"
        cmd = ["awslocal", "s3", "cp", local_path, s3_path]

        # Progress indicator
        print(f"\rUploading {idx}/{total} ({idx/total:.1%})", end='', flush=True)

        try:
            if os.name == "nt":
                subprocess.run(" ".join(cmd), check=True, shell = True)
            else:
                subprocess.run(cmd, check=True)

        except subprocess.CalledProcessError as e:
            # Log error and continue
            print(f"\nError uploading {fname}: {e}")
            continue

    # Final summary
    print()  # Move to next line after progress
    print(f"Done: attempted {total} uploads.")

if __name__ == "__main__":
    main()
