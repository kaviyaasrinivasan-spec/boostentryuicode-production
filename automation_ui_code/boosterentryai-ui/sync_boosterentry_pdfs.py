#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sync missing PDFs from /root/Boostentry_AI_Doc_Processing/{Failed,Inprogress,Processed,Ready_to_Run}
into Docker container 'boosterentryai_container', checking both /pdf_pull and /uploaded_docs.

Default behavior:
- If a local PDF's basename is not present in either /pdf_pull or /uploaded_docs inside the container,
  copy it to /pdf_pull (create dir if needed).
- If already present in either dir, skip.

Options:
- --copy-to-both : when a file is missing in both, copy to BOTH /pdf_pull AND /uploaded_docs.

Run safe repeatedly (idempotent): compares by filename only.
"""

import io
import os
import sys
import tarfile
from pathlib import Path
from typing import Iterable, List, Set, Tuple

try:
    import docker
    from docker.models.containers import Container
except ImportError:
    print("ERROR: This script requires the 'docker' package. Install: pip install docker", file=sys.stderr)
    sys.exit(1)


# ---------- config constants (as requested) ----------
LOCAL_ROOT = Path("/root/Boostentry_AI_Doc_Processing")
LOCAL_SUBDIRS = ["Failed", "Inprogress", "Processed", "Ready_to_Run"]

CONTAINER_NAME = "boosterentryai_container"
CONTAINER_DIR_A = "/app/pdf_pull"
CONTAINER_DIR_B = "/app/uploaded_docs"

DEFAULT_TARGET = CONTAINER_DIR_A  # where to place new files by default


# ---------- helpers ----------
def find_local_pdfs(root: Path, subdirs: List[str]) -> List[Path]:
    pdfs: List[Path] = []
    for sd in subdirs:
        p = (root / sd).resolve()
        if not p.exists():
            print(f"⚠️  Local path not found: {p}")
            continue
        if p.is_file() and p.suffix.lower() == ".pdf":
            pdfs.append(p)
            continue
        if p.is_dir():
            for fp in p.rglob("*.pdf"):
                try:
                    if fp.is_file():
                        pdfs.append(fp.resolve())
                except Exception:
                    pass
    return pdfs


def exec_ok(container: Container, cmd: str) -> Tuple[int, str]:
    rc, out = container.exec_run(["/bin/sh", "-lc", cmd], stdout=True, stderr=True)
    text = out.decode("utf-8", errors="ignore") if isinstance(out, (bytes, bytearray)) else str(out)
    return int(rc), text


def ensure_dir(container: Container, directory: str) -> None:
    rc, out = exec_ok(container, f"mkdir -p {shq(directory)}")
    if rc != 0:
        raise RuntimeError(f"mkdir failed for {directory!r}: {out}")


def list_pdf_basenames(container: Container, directory: str) -> Set[str]:
    rc, out = exec_ok(container, f"test -d {shq(directory)} && ls -1 {shq(directory)} || true")
    names: Set[str] = set()
    for line in out.splitlines():
        name = line.strip()
        if name and name.lower().endswith(".pdf"):
            names.add(name)
    return names


def shq(s: str) -> str:
    if not s:
        return "''"
    return "'" + s.replace("'", "'\"'\"'") + "'"


def tar_single_file_bytes(src: Path, arcname: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        info = tf.gettarinfo(str(src), arcname=arcname)
        info.mode = 0o644
        with src.open("rb") as f:
            tf.addfile(info, fileobj=f)
    buf.seek(0)
    return buf.read()


def copy_one(container: Container, src: Path, dest_dir: str, dry_run: bool = False) -> None:
    ensure_dir(container, dest_dir)
    tar_bytes = tar_single_file_bytes(src, src.name)
    if dry_run:
        print(f"DRY-RUN: {src} -> {dest_dir}/{src.name}")
        return
    ok = container.put_archive(path=dest_dir, data=tar_bytes)
    if not ok:
        raise RuntimeError(f"put_archive returned False for {src} -> {dest_dir}")
    print(f"✅ Copied: {src} -> {dest_dir}/{src.name}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Sync Boostentry PDFs into Docker container.")
    ap.add_argument("--dry-run", action="store_true", help="Plan only; do not copy files")
    ap.add_argument("--copy-to-both", action="store_true",
                    help="When a file is missing in both container dirs, copy to BOTH /pdf_pull and /uploaded_docs")
    args = ap.parse_args(argv)

    # Gather local PDFs
    print(f"🔎 Scanning {LOCAL_ROOT} subdirs: {', '.join(LOCAL_SUBDIRS)}")
    local_pdfs = find_local_pdfs(LOCAL_ROOT, LOCAL_SUBDIRS)
    print(f"📄 Found {len(local_pdfs)} PDF(s) locally.")

    # Connect Docker
    client = docker.from_env()
    try:
        container = client.containers.get(CONTAINER_NAME)
    except Exception as e:
        print(f"❌ Cannot find container {CONTAINER_NAME!r}: {e}", file=sys.stderr)
        return 2

    print(f"🐳 Container: {container.name} ({container.short_id})")
    print(f"📁 Checking container dirs: {CONTAINER_DIR_A} , {CONTAINER_DIR_B}")

    try:
        names_a = list_pdf_basenames(container, CONTAINER_DIR_A)
        names_b = list_pdf_basenames(container, CONTAINER_DIR_B)
        print(f"📦 {CONTAINER_DIR_A}: {len(names_a)} PDFs")
        print(f"📦 {CONTAINER_DIR_B}: {len(names_b)} PDFs")

        copied = 0
        skipped = 0
        errors = 0

        for pdf in local_pdfs:
            name = pdf.name
            if (name in names_a) or (name in names_b):
                skipped += 1
                # (optional) uncomment below to see every skip
                # print(f"⏭️  Already present: {name}")
                continue

            try:
                if args.copy_to_both:
                    copy_one(container, pdf, CONTAINER_DIR_A, dry_run=args.dry_run)
                    copy_one(container, pdf, CONTAINER_DIR_B, dry_run=args.dry_run)
                    names_a.add(name); names_b.add(name)
                else:
                    # default: copy only to DEFAULT_TARGET (/pdf_pull)
                    dest = DEFAULT_TARGET
                    copy_one(container, pdf, dest, dry_run=args.dry_run)
                    if dest.rstrip("/") == CONTAINER_DIR_A.rstrip("/"):
                        names_a.add(name)
                    else:
                        names_b.add(name)
                copied += 1
            except Exception as e:
                errors += 1
                print(f"❌ Copy failed for {pdf}: {e}")

        print("\n==== Sync summary ====")
        print(f"Copied: {copied}")
        print(f"Skipped (already in container): {skipped}")
        print(f"Errors: {errors}")
        if args.dry_run:
            print("(dry-run: no files actually copied)")
        return 0 if errors == 0 else 3

    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
