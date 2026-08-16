import argparse
import io
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import nbtlib
import tzlocal

from .addons.voxy import clean_voxy_cache
from .anvil import RegionFile
from .cleaner import ChunkStats, Cleaner
from .menu import select_mods_interaction

logger = logging.getLogger(__name__)


def find_region_directories(world: Path) -> list[Path]:
        directories: list[Path] = []
        for dir in world.rglob("region"):
                if dir.is_dir():
                        directories.append(dir)
        entities_path = world / "entities"
        if entities_path.is_dir():
                directories.append(entities_path)
        return directories


def backup_world(world: Path) -> Path:
        timestamp = datetime.now(tzlocal.get_localzone()).strftime("%Y%m%d_%H%M%S")
        backup_path = world.parent / f"{world.name}_backup_{timestamp}"
        print(f"\nBackuing up to {backup_path}")
        _ = shutil.copytree(world, backup_path, symlinks=True)
        print("Backup complete.")
        return backup_path


def process_dimension(
        region_path: Path, cleaner: Cleaner, *, dry: bool = False
) -> ChunkStats:
        mca_count = sorted(region_path.glob("*.mca"))
        if not mca_count:
                return ChunkStats()

        dimension = region_path.parent.name
        dimension_stats = ChunkStats()

        print(f"\n{'=' * 60}")
        print(f"  {dimension}  ({len(mca_count)} files)")
        print(f"{'=' * 60}")

        for mca in mca_count:
                region = RegionFile(mca)
                region.read_header()

                file_stats = ChunkStats()
                modified: dict[tuple[int, int], bytes] = {}

                for chunk_x, chunk_z, raw in region.iterate_chunks():
                        if not raw:
                                continue
                        chunk = nbtlib.File.parse(io.BytesIO(raw))

                        chunk_stats = cleaner.clean_chunk(chunk)
                        if chunk_stats:
                                file_stats += chunk_stats
                                if not dry:
                                        buffer = io.BytesIO()
                                        chunk.write(buffer)
                                        modified[(chunk_x, chunk_z)] = buffer.getvalue()
                if file_stats:
                        print(
                                f"  {mca.name}: "
                                + f"blocks={file_stats.blocks} block_entities={file_stats.block_entities} "
                                + f"entities={file_stats.entities} items={file_stats.items} "
                                + f"attachments={file_stats.attachments} structures={file_stats.structures}"
                        )
                        dimension_stats += file_stats

                if modified and not dry:
                        for chunk_x, chunk_z, raw in region.iterate_chunks():
                                if (chunk_x, chunk_z) not in modified:
                                        modified[(chunk_x, chunk_z)] = raw
                        region.write(modified)

        print(
                f"\n  --- {dimension} total: "
                + f"{dimension_stats.blocks} blocks, {dimension_stats.block_entities} block entities, "
                + f"{dimension_stats.entities} entities, {dimension_stats.items} items, "
                + f"{dimension_stats.attachments} attachments, {dimension_stats.structures} structures ---"
        )

        return dimension_stats


def main() -> None:
        ap = argparse.ArgumentParser(description="Strip mod data from Minecraft worlds")
        _ = ap.add_argument("world", help="Path to world folder")
        _ = ap.add_argument(
                "-d", "--dry-run", action="store_true", help="Preview before running"
        )
        _ = ap.add_argument("--no-backup", action="store_true", help="Skip backup")
        _ = ap.add_argument(
                "--no-voxy", action="store_true", help="Skip Voxy cache clearing"
        )
        args = ap.parse_args()

        world = Path(args.world)
        if not world.is_dir():
                print(f"ERROR: Not a directory: {world}")
                sys.exit(1)

        regions = find_region_directories(world)
        if not regions:
                print("No region/ folders found.")
                sys.exit(1)

        namespaces = select_mods_interaction()

        cleaner = Cleaner(namespaces=namespaces)

        print(f"\n World:     {world}")
        print(f"Mod(s):    {', '.join(namespaces)}")
        print(f"Mode:      {'DRY RUN' if args.dry_run else 'LIVE'}")
        print(f"Region folders: {len(regions)}")
        for region_file in regions:
                count = len(list(region_file.glob("*.mca")))
                print(f"  {region_file.parent.name}/region  ({count} .mca)")
        if not args.dry_run and not args.no_backup:
                _ = backup_world(world)

        print(f"\n{'=' * 60}")
        print("  Cleaning level.dat & playerdata...")
        print(f"{'=' * 60}")
        ld_count = cleaner.clean_level_dat(world, dry=args.dry_run)
        pd_total, pd_files = cleaner.clean_playerdata(world, dry=args.dry_run)

        if not args.no_voxy:
                print(f"\n{'=' * 60}")
                print("  Cleaning Voxy cache...")
                print(f"{'=' * 60}")
                clean_voxy_cache(world, dry=args.dry_run)

        grand_total = ChunkStats()
        for region_file in regions:
                grand_total += process_dimension(region_file, cleaner, dry=args.dry_run)

        print(f"\n{'=' * 60}")
        print("       GRAND TOTAL      AMOUNT")
        print(f"           Blocks:      {grand_total.blocks}")
        print(f"  Blocks Entities:      {grand_total.block_entities}")
        print(f"         Entities:      {grand_total.entities}")
        print(f"            Items:      {grand_total.items}")
        print(f"       Structures:      {grand_total.structures}")
        print(f"      Attachments:      {grand_total.attachments}")
        print(f"        level.dat:      {ld_count}")
        print(f"       playerdata:      {pd_total} attachments ({pd_files} files)")
        print(f"{'=' * 60}")

        if args.dry_run:
                print("\n[DRY RUN] No changes made. Remove --dry-run to apply.")
        else:
                print("\nDone. Test the world in Minecraft.")


if __name__ == "__main__":
        main()
