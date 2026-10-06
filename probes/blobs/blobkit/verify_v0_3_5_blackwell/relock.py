"""verify_v0_3_5_blackwell/relock.py — regenerate _locks.json for the
JAX-floor change (sim_gpu.py install advice). Follows verify_v03/relock.py:
only soup/sim_gpu.py may drift (asserted; anything else aborts). The
packages/blobkit/pyproject.toml extras and README are not in the lock table.

Companion evidence: RECEIPTS.md (full pytest --require-gpu gate runs on
Blackwell B300 with JAX 0.11.2, cuda12 and cuda13 wheels)."""
import hashlib, json, os, sys, time

PKG = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "packages", "blobkit", "blobkit"))
LOCKS = os.path.join(PKG, "_locks.json")

RELOCKED = ["soup/sim_gpu.py"]


def sha(p):
    h = hashlib.sha256()
    h.update(open(p, "rb").read())
    return h.hexdigest()


def main():
    old = json.load(open(LOCKS))
    drift = []
    for rel, want in old["files"].items():
        got = sha(os.path.join(PKG, rel))
        if got != want and rel not in RELOCKED:
            drift.append((rel, want[:12], got[:12]))
    if drift:
        print("UNEXPECTED DRIFT (abort):", drift)
        sys.exit(1)
    files = dict(old["files"])
    for rel in RELOCKED:
        files[rel] = sha(os.path.join(PKG, rel))
    out = dict(locked_at=time.strftime("%Y-%m-%d %H:%M:%S"),
               version=old.get("version", "0.3.5"),
               files=dict(sorted(files.items())))
    json.dump(out, open(LOCKS, "w"), indent=1)
    print(f"locked {len(files)} files (was {len(old['files'])}); "
          f"relocked {RELOCKED}")


if __name__ == "__main__":
    main()
