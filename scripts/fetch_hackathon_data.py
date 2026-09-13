"""
File:    scripts/fetch_hackathon_data.py

Spec:    Downloads the Glider Rodeo hackathon dataset from its public Google
         Cloud Storage bucket into the local data/ folder. This is a ONE-TIME
         setup step: run it once, then every notebook reads local files instead
         of talking to Google Cloud. Re-running is safe -- files you already
         have are skipped.

         The bucket is public, so no Google account, login or credentials are
         needed. Only the Python standard library is used.

Usage:   python3 scripts/fetch_hackathon_data.py               # show what is available
         python3 scripts/fetch_hackathon_data.py sg274         # download one deployment
         python3 scripts/fetch_hackathon_data.py sg274 risso   # download several
         python3 scripts/fetch_hackathon_data.py --all         # download everything

Inputs:  None. Reads the public bucket named below.

Outputs: Files written into data/, keeping the folder layout of the bucket.
         Nothing in data/ is committed to git -- see .gitignore.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BUCKET = "glider-rodeo-data"
PREFIX = "Glider Rodeo Hackathon"

API = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"

# Where the files land. Resolved relative to the repo, so the script works no
# matter which folder you run it from.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Junk that macOS leaves in shared folders.
SKIP_NAMES = {".DS_Store"}


def human(num_bytes):
    """Format a byte count for display, e.g. 4.2 MB."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024


def list_objects():
    """Return every object in the bucket under PREFIX, following pagination."""
    objects = []
    page_token = None

    while True:
        query = {"prefix": PREFIX, "maxResults": 1000}
        if page_token:
            query["pageToken"] = page_token

        with urllib.request.urlopen(f"{API}?{urllib.parse.urlencode(query)}", timeout=60) as response:
            payload = json.load(response)

        objects.extend(payload.get("items", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return [
        obj for obj in objects
        if not obj["name"].endswith("/") and Path(obj["name"]).name not in SKIP_NAMES
    ]


def download(obj, destination):
    """Download one object to destination, via a .part file so an interrupted
    download never leaves a half-written file looking complete."""
    url = f"{API}/{urllib.parse.quote(obj['name'], safe='')}?alt=media"
    partial = destination.with_suffix(destination.suffix + ".part")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as response, open(partial, "wb") as handle:
        while chunk := response.read(1024 * 256):
            handle.write(chunk)

    partial.replace(destination)


def group_by_deployment(objects):
    """Group objects by the folder directly under the prefix."""
    groups = {}
    for obj in objects:
        parts = obj["name"].split("/")
        folder = parts[1] if len(parts) > 2 else "(top level)"
        groups.setdefault(folder, []).append(obj)
    return groups


def show_inventory(objects):
    """Print what is in the bucket and how to ask for it."""
    groups = group_by_deployment(objects)
    total = sum(int(o["size"]) for o in objects)

    print(f"The hackathon dataset has {len(objects)} files, {human(total)} in total.\n")
    print(f"  {'deployment':22s} {'files':>5s}  {'size':>9s}")
    print(f"  {'-' * 22} {'-' * 5}  {'-' * 9}")

    for name in sorted(groups):
        files = groups[name]
        size = sum(int(o["size"]) for o in files)
        print(f"  {name:22s} {len(files):5d}  {human(size):>9s}")

    print("\nDownload one deployment (recommended to start):\n")
    example = next(n for n in sorted(groups) if n != "(top level)")
    print(f"    python3 scripts/fetch_hackathon_data.py {example}\n")
    print("Or download everything:\n")
    print(f"    python3 scripts/fetch_hackathon_data.py --all\n")
    print(f"Everything is {human(total)}, so it takes a while. If you are working in")
    print("Binder, remember the session is erased when you close it.")


def main(argv):
    print(f"Source: gs://{BUCKET}/{PREFIX}  (public, no login needed)\n")

    try:
        objects = list_objects()
    except urllib.error.HTTPError as exc:
        print(f"Could not read the bucket (HTTP {exc.code}).")
        print("It may have stopped being public. Ask the organisers to check.")
        return 1
    except urllib.error.URLError as exc:
        print(f"Could not reach Google Cloud Storage: {exc.reason}")
        print("Check your internet connection and try again.")
        return 1

    if not objects:
        print(f"No files found under gs://{BUCKET}/{PREFIX}")
        return 1

    # No arguments: show what is on offer rather than pulling gigabytes unasked.
    if not argv:
        show_inventory(objects)
        return 0

    if argv == ["--all"]:
        wanted = objects
    else:
        wanted = [o for o in objects if any(term.lower() in o["name"].lower() for term in argv)]
        if not wanted:
            print(f"Nothing matched: {' '.join(argv)}")
            print("Run with no arguments to see what is available.")
            return 1

    total = sum(int(o["size"]) for o in wanted)
    print(f"Downloading {len(wanted)} file(s), {human(total)} into {DATA_DIR}\n")

    downloaded = skipped = fetched_bytes = 0

    for obj in sorted(wanted, key=lambda o: o["name"]):
        # Strip the bucket prefix so data/ mirrors the layout inside the bucket.
        relative = obj["name"][len(PREFIX):].lstrip("/")
        destination = DATA_DIR / relative

        if destination.exists() and destination.stat().st_size == int(obj["size"]):
            print(f"  skip      {relative}")
            skipped += 1
            continue

        print(f"  download  {relative}  ({human(int(obj['size']))})", flush=True)
        try:
            download(obj, destination)
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            print(f"            FAILED: {exc}")
            continue

        fetched_bytes += destination.stat().st_size
        downloaded += 1

    print()
    print(f"Done. {downloaded} downloaded ({human(fetched_bytes)}), {skipped} already present.")
    print(f"The data is in {DATA_DIR} and is ignored by git.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
