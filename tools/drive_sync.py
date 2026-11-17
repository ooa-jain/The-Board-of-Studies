"""Google Drive for the uploaded files — check, send, and tidy.

    cd /var/www/jain-bos-portal
    venv/bin/python tools/drive_sync.py --check     # can the portal reach the Drive script?
    venv/bin/python tools/drive_sync.py --push      # send every file not yet in Drive
    venv/bin/python tools/drive_sync.py --status    # how many are in Drive, how many not
    venv/bin/python tools/drive_sync.py --prune     # delete server copies already in Drive

--push is safe to run again and again: a file already in Drive is skipped.
--prune only removes server copies of files Drive confirms it holds; the
portal fetches a file back from Drive the next time it is opened. It asks
before deleting anything (add --yes to skip the question).

Settings come from .env: DRIVE_SCRIPT_URL and DRIVE_SCRIPT_SECRET (see
app/drive_store.py and deploy/drive_script.gs).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app import drive_store as D  # noqa: E402
from app.db import get_db  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true", help="test the connection to the Drive script")
    p.add_argument("--push", action="store_true", help="send every file not yet in Drive")
    p.add_argument("--status", action="store_true", help="count files in Drive and not")
    p.add_argument("--prune", action="store_true", help="delete server copies of files already in Drive")
    p.add_argument("--yes", action="store_true", help="do not ask before --prune deletes")
    a = p.parse_args(argv)
    if not (a.check or a.push or a.status or a.prune):
        p.print_help()
        return 0

    app = create_app()
    with app.app_context():
        if not D.configured():
            print("DRIVE_SCRIPT_URL and DRIVE_SCRIPT_SECRET are not set in .env.")
            return 1
        db = get_db()

        if a.check:
            try:
                out = D.ping()
            except D.DriveError as e:
                print(f"Not connected: {e}")
                return 1
            print(f"Connected. Files go into the Drive folder “BoS Portal Files” "
                  f"(https://drive.google.com/drive/folders/{out['root']}).")
            print("New uploads are sent to Drive: " + ("yes (FILE_STORE=drive)" if D.enabled()
                  else "not yet — set FILE_STORE=drive in .env and restart the portal"))

        if a.push:
            todo = list(db.files.find({"drive_id": {"$exists": False}}))
            print(f"{len(todo)} file(s) to send.")
            sent = missing = failed = 0
            for i, r in enumerate(todo, 1):
                if not D.local_path(r).exists():
                    missing += 1
                    continue
                print(f"\r  {i}/{len(todo)}  {r['dept_code']} · {r['original_name'][:50]}" + " " * 20,
                      end="", flush=True)
                if D.push(r):
                    sent += 1
                else:
                    failed += 1
            print(f"\nSent {sent}." + (f" {failed} failed (run --push again)." if failed else "")
                  + (f" {missing} not on the server, so not sent." if missing else ""))

        if a.status or a.push:
            total = db.files.count_documents({})
            inside = db.files.count_documents({"drive_id": {"$exists": True}})
            errs = db.files.count_documents({"drive_error": {"$exists": True}})
            print(f"In Drive: {inside} of {total} file(s)." + (f" {errs} with an error last time." if errs else ""))

        if a.prune:
            recs = [r for r in db.files.find({"drive_id": {"$exists": True}}) if D.local_path(r).exists()]
            size = sum(D.local_path(r).stat().st_size for r in recs)
            if not recs:
                print("No server copies to remove.")
                return 0
            print(f"{len(recs)} server copie(s) of files already in Drive, {size / 1048576:.1f} MB.")
            if not a.yes and input("Delete them from the server? Type yes: ").strip().lower() != "yes":
                print("Nothing was deleted.")
                return 0
            for r in recs:
                path = D.local_path(r)
                path.unlink(missing_ok=True)
                path.with_suffix(path.suffix + ".thumb.png").unlink(missing_ok=True)
            print(f"Removed {len(recs)}. They are fetched back from Drive when opened.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
