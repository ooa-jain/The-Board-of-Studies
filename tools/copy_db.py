"""Copy the portal's database to another MongoDB (another Atlas cluster).

    cd /var/www/jain-bos-portal
    venv/bin/python tools/copy_db.py

The source is the portal's own database, as .env names it (MONGO_URI and
MONGO_DB). The target connection string is asked for, hidden as it is typed,
and never printed. Every collection is copied with its indexes, and the
counts are compared at the end. The source is only read, never changed.

It stops if the target database already holds data, unless --replace is
given (which empties the target collections it copies into first).
Afterwards, put the new connection string in .env as MONGO_URI and restart
the portal.
"""
import argparse
import getpass
import sys
from pathlib import Path

from dotenv import dotenv_values
from pymongo import MongoClient

BATCH = 500


def hide(uri: str) -> str:
    """The connection string with its password masked, for messages."""
    if "@" in uri and "//" in uri:
        head, rest = uri.split("//", 1)
        return head + "//***@" + rest.split("@", 1)[1]
    return uri


def copy(src_db, dst_db, replace=False, out=print):
    names = sorted(n for n in src_db.list_collection_names() if not n.startswith("system."))
    taken = [n for n in dst_db.list_collection_names() if dst_db[n].estimated_document_count()]
    if taken and not replace:
        out(f"The target database '{dst_db.name}' already has data in: {', '.join(sorted(taken))}.")
        out("Nothing was copied. Run again with --replace to overwrite those collections.")
        return False
    report = []
    for name in names:
        src, dst = src_db[name], dst_db[name]
        if replace:
            dst.delete_many({})
        batch, n = [], 0
        for doc in src.find({}, no_cursor_timeout=False):
            batch.append(doc)
            if len(batch) >= BATCH:
                dst.insert_many(batch, ordered=False)
                n += len(batch)
                batch = []
        if batch:
            dst.insert_many(batch, ordered=False)
            n += len(batch)
        for idx in src.list_indexes():
            if idx["name"] == "_id_":
                continue
            opts = {k: v for k, v in idx.items() if k not in ("v", "key", "ns")}
            dst.create_index(list(idx["key"].items()), **opts)
        report.append((name, src.count_documents({}), dst.count_documents({})))
        out(f"  {name:<20} {n} copied")
    ok = all(a == b for _, a, b in report)
    out("")
    for name, a, b in report:
        out(f"  {name:<20} source {a:>6}   target {b:>6}   {'ok' if a == b else 'DIFFERENT'}")
    out("")
    out("All collections copied and counted." if ok else "Some counts differ — check before switching over.")
    return ok


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--env", default=str(Path(__file__).resolve().parent.parent / ".env"))
    p.add_argument("--target-db", help="database name on the target (default: the same name)")
    p.add_argument("--replace", action="store_true", help="overwrite collections that already have data")
    a = p.parse_args(argv)
    env = dotenv_values(a.env)
    src_uri, src_name = env.get("MONGO_URI"), env.get("MONGO_DB") or "jain_bos_portal"
    if not src_uri:
        sys.exit(f"MONGO_URI is not set in {a.env}")
    dst_uri = getpass.getpass("Target MongoDB connection string (hidden): ").strip()
    if not dst_uri:
        sys.exit("No target given. Nothing was copied.")
    dst_name = a.target_db or src_name
    print(f"From {hide(src_uri)}  database '{src_name}'")
    print(f"To   {hide(dst_uri)}  database '{dst_name}'")
    src = MongoClient(src_uri, serverSelectionTimeoutMS=15000)
    dst = MongoClient(dst_uri, serverSelectionTimeoutMS=15000)
    src.admin.command("ping")
    dst.admin.command("ping")
    ok = copy(src[src_name], dst[dst_name], replace=a.replace)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
