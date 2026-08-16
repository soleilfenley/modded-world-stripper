import shutil
from pathlib import Path


def clean_voxy_cache(world: Path, *, dry: bool = False) -> None:
        voxy_path = world / "voxy"
        if not voxy_path.is_dir():
                return

        size_mb = sum(
                file.stat().st_size for file in voxy_path.rglob("*") if file.is_file()
        ) / (1024 * 1024)
        print(f"  voxy/cache: {size_mb:.1f} MB")

        if dry:
                print("  [DRY RUN] would move voxy/ to voxy.bak/")
        else:
                backup_path = str(voxy_path) + ".bak"
                if Path(backup_path).exists():
                        shutil.rmtree(backup_path)
                _ = shutil.move(str(voxy_path), backup_path)
                print("  voxy/ moved to voxy.bak/ (will regenerate on next launch)")
