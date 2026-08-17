import argparse
import io
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import nbtlib
import tzlocal

from .addons import clean_voxy_cache
from .anvil import RegionFile
from .cleaner import ChunkStats, Cleaner
from .ui import ProgressBar, select_mods_interaction

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


def process_dimension(region_path: Path, cleaner: Cleaner, progress: ProgressBar, *, dry: bool = False) -> ChunkStats:
        mca_files = sorted(region_path.glob("*.mca"))
        if not mca_files:
                return ChunkStats()

        dimension = (region_path.name if region_path.name == "entities" else region_path.parent.name)
        dimension_stats = ChunkStats()

        for mca in mca_files:
                progress.advance(f"{dimension}/{mca.name}")
                try:
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
        
                        if modified and not dry:
                                for chunk_x, chunk_z, raw in region.iterate_chunks():
                                        if (chunk_x, chunk_z) not in modified:
                                                modified[(chunk_x, chunk_z)] = raw
                                region.write(modified)

                        dimension_stats += file_stats
                except Exception:
                        progress.fail()
                        print(f"\nERROR: failed while processing region {dimension}/{mca.name}")
                        raise

        return dimension_stats


def main() -> None:
        ap = argparse.ArgumentParser(description="Strip mod data from Minecraft worlds")
        _ = ap.add_argument("world", help="Path to world folder")
        _ = ap.add_argument("--dry-run", "-d", action="store_true", help="Preview before running")
        _ = ap.add_argument("--no-backup", action="store_true", help="Skip backup")
        _ = ap.add_argument("--no-voxy", action="store_true", help="Skip Voxy cache clearing")
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

        total_files = sum(len(list(region.glob("*.mca"))) for region in regions)

        print(f"\n{'=' * 60}")
        print(f"  Cleaning {total_files} region file(s)...")
        print(f"{'=' * 60}")

        progress = ProgressBar(total_files, "Cleaning")
        grand_total = ChunkStats()
        per_dimension: list[tuple[str, ChunkStats]] = []

        for region_file in regions:
                dimension_stats = process_dimension(region_file, cleaner, progress, dry=args.dry_run)
                per_dimension.append((region_file.parent.name, dimension_stats))
                grand_total += dimension_stats

        progress.finish()

        print(f"\n{'=' * 60}")
        print("  PER-DIMENSION")
        print(f"{'=' * 60}")
        for name, stats in per_dimension:
                if not stats:
                        continue
                print(
			f"  {name}: "
			+ f"blocks={stats.blocks} block_entities={stats.block_entities} "
			+ f"entities={stats.entities} items={stats.items} "
			+ f"attachments={stats.attachments} structures={stats.structures}"
		)
		
        print(f"\n{'=' * 60}")
        print("       GRAND TOTAL      AMOUNT")
        print(f"           Blocks:      {grand_total.blocks}")
        print(f"  Blocks Entities:      {grand_total.block_entities}")
        print(f"         Entities:      {grand_total.entities}")
        print(f"            Items:      {grand_total.items}")
        print(f"      Attachments:      {grand_total.attachments}")
        print(f"       Structures:      {grand_total.structures}")
        print(f"        level.dat:      {ld_count}")
        print(f"       playerdata:      {pd_total} attachments ({pd_files} files)")
        print(f"{'=' * 60}")
        
        if args.dry_run:
                print("\n[DRY RUN] No changes made. Remove --dry-run to apply.")
        else:
                print("\nDone. Test the world in Minecraft.")


if __name__ == "__main__":
        main()
