#!/usr/bin/env python3
"""
strip_supplementaries.py -- Offline world cleaner for NeoForge 1.21.1

Recursively removes all Supplementaries mod data from Minecraft Anvil region
files while preserving builds, terrain, and unrelated NBT.

Usage:
    python strip_supplementaries.py "C:/path/to/world"           # live run
    python strip_supplementaries.py "C:/path/to/world" --dry-run # preview only
    python strip_supplementaries.py "C:/path/to/world" --no-backup # skip backup

Requirements: Python 3.9+, nbtlib (pip install nbtlib)
"""

import argparse
import gzip
import io
import logging
import shutil
import struct
import sys
import zlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import nbtlib

MOD_NS = "supplementaries"
SECTOR = 4096
HEADER = SECTOR * 2

logger = logging.getLogger(__name__)


def clean_level_dat(world, dry=False):
        lp = Path(world) / "level.dat"
        if not lp.exists():
                print("  level.dat not found, skipping.")
                return {"level_dat": 0}

        with open(lp, "rb") as f:
                raw = f.read()
        data = nbtlib.File.parse(io.BytesIO(gzip.decompress(raw)))
        player = data["Data"]["Player"]
        attachments = player.get("neoforge:attachments", {})
        n = 0
        for k in list(attachments):
                if MOD_NS in str(k):
                        del attachments[k]
                        n += 1
        if n > 0:
                print(f"  level.dat: {n} attachment(s) stripped")
        if not dry:
                shutil.copy2(lp, str(lp) + ".bak")
                buf = io.BytesIO()
                data.write(buf)
                with open(lp, "wb") as f:
                        f.write(gzip.compress(buf.getvalue()))
        return {"level_dat": n}


def clean_playerdata(world, dry=False):
        pd = Path(world) / "playerdata"
        if not pd.is_dir():
                print("  playerdata/ not found, skipping.")
                return {"playerdata": 0, "playerdata_files": 0}

        total = 0
        files = 0
        for fp in sorted(pd.glob("*.dat")):
                if fp.suffix != ".dat" or ".bak" in fp.name or "_old" in fp.name:
                        continue
                with open(fp, "rb") as f:
                        raw = f.read()
                data = nbtlib.File.parse(io.BytesIO(gzip.decompress(raw)))
                attachments = data.get("neoforge:attachments") or {}
                n = 0
                for k in list(attachments):
                        if MOD_NS in str(k):
                                del attachments[k]
                                n += 1
                if n > 0:
                        total += n
                        files += 1
                        print(f"  playerdata/{fp.name}: {n} attachment(s) stripped")
                        if not dry:
                                shutil.copy2(fp, str(fp) + ".bak")
                                buf = io.BytesIO()
                                data.write(buf)
                                with open(fp, "wb") as f:
                                        f.write(gzip.compress(buf.getvalue()))
        return {"playerdata": total, "playerdata_files": files}


def read_header(f):
        locs = []
        for _ in range(1024):
                r = f.read(4)
                locs.append(((r[0] << 16) | (r[1] << 8) | r[2], r[3]))
        ts = list(struct.unpack(">1024I", f.read(4096)))
        return locs, ts


def read_chunk(f, offset, sectors):
        if offset == 0 or sectors == 0:
                return None
        f.seek(offset * SECTOR)
        length = struct.unpack(">I", f.read(4))[0]
        comp = f.read(1)[0]
        data = f.read(length - 1)
        if comp == 2:
                return zlib.decompress(data)
        if comp == 1:
                return gzip.decompress(data)
        return data


def write_region(path, chunks):
        loc_tab = bytearray(4096)
        ts_tab = bytearray(4096)
        sector_data = bytearray()
        cur = 2
        for idx in range(1024):
                cx, cz = idx % 32, idx // 32
                key = (cx, cz)
                if key in chunks and chunks[key] is not None:
                        compressed = zlib.compress(chunks[key])
                        payload = (
                                struct.pack(">I", len(compressed) + 1)
                                + b"\x02"
                                + compressed
                        )
                        need = (len(payload) + SECTOR - 1) // SECTOR
                        padded = payload + b"\x00" * (need * SECTOR - len(payload))
                        struct.pack_into(">I", loc_tab, idx * 4, (cur << 8) | need)
                        sector_data.extend(padded)
                        cur += need
        with open(path, "wb") as f:
                f.write(loc_tab)
                f.write(ts_tab)
                f.write(sector_data)


def clean_items(container):
        mod = False
        for key in ("Items", "Inventory", "items", "inventory"):
                if key not in container:
                        continue
                items = container[key]
                rm = []
                for i, item in enumerate(items):
                        if hasattr(item, "get") and str(item.get("id", "")).startswith(
                                f"{MOD_NS}:"
                        ):
                                rm.append(i)
                        if "tag" in item and "BlockEntityTag" in item["tag"]:
                                clean_items(item["tag"]["BlockEntityTag"])
                for i in reversed(rm):
                        del items[i]
                        mod = True
        return mod


def strip_attachments(compound):
        n = 0
        for k in list(compound):
                if MOD_NS in str(k):
                        del compound[k]
                        n += 1
        return n


def clean_chunk(chunk):
        s = {
                "blocks": 0,
                "block_entities": 0,
                "entities": 0,
                "items": 0,
                "attachments": 0,
        }
        if "sections" in chunk:
                for sec in chunk["sections"]:
                        bs = sec.get("block_states")
                        if bs is None or "palette" not in bs:
                                continue
                        for i in range(len(bs["palette"])):
                                if str(bs["palette"][i].get("Name", "")).startswith(
                                        f"{MOD_NS}:"
                                ):
                                        bs["palette"][i] = nbtlib.Compound(
                                                {"Name": nbtlib.String("minecraft:air")}
                                        )
                                        s["blocks"] += 1
        if "block_entities" in chunk:
                rm = []
                for i, be in enumerate(chunk["block_entities"]):
                        if str(be.get("id", "")).startswith(f"{MOD_NS}:"):
                                rm.append(i)
                        else:
                                if clean_items(be):
                                        s["items"] += 1
                                s["attachments"] += strip_attachments(be)
                for i in reversed(rm):
                        del chunk["block_entities"][i]
                        s["block_entities"] += 1
        if "entities" in chunk:
                rm = []
                for i, e in enumerate(chunk["entities"]):
                        if str(e.get("id", "")).startswith(f"{MOD_NS}:"):
                                rm.append(i)
                        elif clean_items(e):
                                s["items"] += 1
                for i in reversed(rm):
                        del chunk["entities"][i]
                        s["entities"] += 1
        s["attachments"] += strip_attachments(chunk)
        if "entities" in chunk:
                for e in chunk["entities"]:
                        s["attachments"] += strip_attachments(e)
        return s


def process_region(path, dry=False):
        st = {
                "blocks": 0,
                "block_entities": 0,
                "entities": 0,
                "items": 0,
                "attachments": 0,
                "chunks": 0,
        }
        with open(path, "rb") as f:
                locs, _ = read_header(f)
                mod_chunks = {}
                for idx in range(1024):
                        off, sec = locs[idx]
                        if off == 0 or sec == 0:
                                continue
                        cx, cz = idx % 32, idx // 32
                        raw = read_chunk(f, off, sec)
                        if raw is None:
                                continue
                        try:
                                chunk = nbtlib.File.parse(io.BytesIO(raw))
                        except Exception as e:
                                logger.exception(f"      [SKIP] ({cx},{cz}): {e}")
                                continue
                        cs = clean_chunk(chunk)
                        if sum(cs.values()) > 0:
                                st["chunks"] += 1
                                for k in st:
                                        if k != "chunks":
                                                st[k] += cs[k]
                                if not dry:
                                        buf = io.BytesIO()
                                        chunk.write(buf)
                                        mod_chunks[(cx, cz)] = buf.getvalue()
        if st["chunks"] > 0 and not dry:
                with open(path, "rb") as f:
                        locs, _ = read_header(f)
                        for idx in range(1024):
                                off, sec = locs[idx]
                                if off == 0 or sec == 0:
                                        continue
                                cx, cz = idx % 32, idx // 32
                                if (cx, cz) in mod_chunks:
                                        continue
                                raw = read_chunk(f, off, sec)
                                if raw is not None:
                                        mod_chunks[(cx, cz)] = raw
                write_region(path, mod_chunks)
        return st


def find_regions(world):
        dirs = []
        for d in Path(world).rglob("region"):
                if d.is_dir():
                        dirs.append(d)
        entities_dir = Path(world) / "entities"
        if entities_dir.is_dir():
                dirs.append(entities_dir)
        return dirs


def clean_voxy_cache(world, dry=False):
        vp = Path(world) / "voxy"
        if not vp.is_dir():
                return

        size_mb = sum(f.stat().st_size for f in vp.rglob("*") if f.is_file()) / (
                1024 * 1024
        )
        print(f"  voxy/ cache: {size_mb:.1f} MB")

        if not dry:
                backup_path = str(vp) + ".bak"
                if Path(backup_path).exists():
                        shutil.rmtree(backup_path)
                shutil.move(str(vp), backup_path)
                print("  voxy/ moved to voxy.bak (will regenerate on next launch)")
        else:
                print("  [DRY RUN] would move voxy/ to voxy.bak")


def backup(world):
        world = Path(world)
        ts = datetime.now(tz=ZoneInfo("America/Chicago")).strftime("%Y%m%d_%H%M%S")
        bp = world.parent / f"{world.name}_backup_{ts}"
        print(f"\nBacking up to: {bp}")
        shutil.copytree(world, bp, symlinks=True)
        print("Backup complete.")
        return bp


def main():
        ap = argparse.ArgumentParser(
                description="Strip Supplementaries from Minecraft worlds"
        )
        ap.add_argument("world", help="Path to world folder")
        ap.add_argument("--dry-run", action="store_true", help="Preview only")
        ap.add_argument("--no-backup", action="store_true", help="Skip backup")
        ap.add_argument(
                "--no-voxy", action="store_true", help="Skip Voxy cache clearing"
        )
        args = ap.parse_args()

        wp = Path(args.world)
        if not wp.is_dir():
                print(f"ERROR: Not a directory: {wp}")
                sys.exit(1)

        regions = find_regions(wp)
        if not regions:
                print("No region/ folders found.")
                sys.exit(1)

        print(f"World: {wp}")
        print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
        print(f"Region folders: {len(regions)}")
        for rf in regions:
                n = len(list(rf.glob("*.mca")))
                print(f"  {rf.parent.name}/region  ({n} .mca)")

        if not args.dry_run and not args.no_backup:
                backup(wp)

        print(f"\n{'=' * 60}")
        print("  Cleaning level.dat & playerdata")
        print(f"{'=' * 60}")
        r1 = clean_level_dat(wp, dry=args.dry_run)
        r2 = clean_playerdata(wp, dry=args.dry_run)

        if not args.no_voxy:
                print(f"\n{'=' * 60}")
                print("  Cleaning voxy cache")
                print(f"{'=' * 60}")
                clean_voxy_cache(wp, dry=args.dry_run)

        gt = {
                "blocks": 0,
                "block_entities": 0,
                "entities": 0,
                "items": 0,
                "attachments": 0,
                "chunks": 0,
        }

        for rf in regions:
                dim = rf.parent.name
                mcas = sorted(rf.glob("*.mca"))
                if not mcas:
                        continue
                dt = {
                        "blocks": 0,
                        "block_entities": 0,
                        "entities": 0,
                        "items": 0,
                        "attachments": 0,
                        "chunks": 0,
                }
                print(f"\n{'=' * 60}")
                print(f"  {dim}  ({len(mcas)} files)")
                print(f"{'=' * 60}")
                for mca in mcas:
                        st = process_region(mca, dry=args.dry_run)
                        if st["chunks"] > 0:
                                print(
                                        f"  {mca.name}: {st['chunks']} chunks | "
                                        f"blk={st['blocks']} be={st['block_entities']} "
                                        f"ent={st['entities']} itm={st['items']} "
                                        f"att={st['attachments']}"
                                )
                                for k in dt:
                                        dt[k] += st[k]
                print(
                        f"  --- {dim} total: {dt['chunks']} chunks, {dt['blocks']} blocks, "
                        f"{dt['block_entities']} be, {dt['entities']} ent, "
                        f"{dt['items']} items, {dt['attachments']} att ---"
                )
                for k in gt:
                        gt[k] += dt[k]

        print(f"\n{'=' * 60}")
        print("  GRAND TOTAL")
        print(f"  Chunks:     {gt['chunks']}")
        print(f"  Blocks:     {gt['blocks']}")
        print(f"  Block ents: {gt['block_entities']}")
        print(f"  Entities:   {gt['entities']}")
        print(f"  Items:      {gt['items']}")
        print(f"  Attachments:{gt['attachments']}")
        print(f"  level.dat:    {r1.get('level_dat')}")
        print(
                f"  playerdata:   {r2.get('playerdata', 0)} attachments ({r2.get('playerdata_files', 0)} files)"
        )
        print(f"{'=' * 60}")

        if args.dry_run:
                print("\n[DRY RUN] No changes made. Remove --dry-run to apply.")
        else:
                print("\nDone. Test the world in Minecraft.")


if __name__ == "__main__":
        main()
