import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

import nbtlib
from typing_extensions import Self

from src.components import read_nbt, write_nbt

logger = logging.getLogger(__name__)


@dataclass
class ChunkStats:
        blocks: int = 0
        block_entities: int = 0
        entities: int = 0
        items: int = 0
        attachments: int = 0

        def __add__(self, other: "ChunkStats") -> "ChunkStats":
                return ChunkStats(
                        blocks=self.blocks + other.blocks,
                        block_entities=self.block_entities + other.block_entities,
                        entities=self.entities + other.entities,
                        items=self.items + other.items,
                        attachments=self.attachments + other.attachments,
                )

        def __iadd__(self, other: "ChunkStats") -> Self:
                self.blocks += other.blocks
                self.block_entities += other.block_entities
                self.entities += other.entities
                self.items += other.items
                self.attachments += other.attachments
                return self

        def __bool__(self) -> bool:
                return any(
                        (
                                self.blocks,
                                self.block_entities,
                                self.entities,
                                self.items,
                                self.attachments,
                        )
                )


class Cleaner:
        def __init__(self, namespaces: str | list[str]) -> None:
                if isinstance(namespaces, str):
                        self._namespaces = [namespaces]
                else:
                        self._namespaces = list(namespaces)

        def _is_mod(self, value: str) -> bool:
                return any (
                        str(value).startswith(f"{namespace}:") for namespace in self._namespaces
                )

        def _has_mod_key(self, nbt_property: str) -> bool:
                return any(namespace in str(nbt_property) for namespace in self._namespaces)

        def clean_items(self, container) -> bool:
                modified = False
                for nbt_property in ("Items", "Inventory", "items", "inventory"):
                        if nbt_property not in container:
                                continue
                        items = container[nbt_property]
                        remove = []
                        for index, item in enumerate(items):
                                if hasattr(item, "get") and self._is_mod(
                                        item.get("id", "")
                                ):
                                        remove.append(index)
                                if "tag" in item and "BlockEntityTag" in item["tag"]:
                                        self.clean_items(item["tag"]["BlockEntityTag"])
                        for index in reversed(remove):
                                del items[index]
                                modified = True
                return modified

        def strip_attachments(self, compound) -> int:
                count = 0
                for nbt_property in list(compound):
                        if self._has_mod_key(nbt_property):
                                del compound[nbt_property]
                                count += 1
                return count

        def clean_chunk(self, chunk) -> ChunkStats:
                stats = ChunkStats()

                if "sections" in chunk:
                        for section in chunk["sections"]:
                                block_state = section.get("block_states")
                                if block_state is None or "palette" not in block_state:
                                        continue
                                for index in range(len(block_state["palette"])):
                                        if self._is_mod(
                                                block_state["palette"][index].get(
                                                        "Name", ""
                                                )
                                        ):
                                                block_state["palette"][index] = (
                                                        nbtlib.Compound(
                                                                {
                                                                        "Name": nbtlib.String(
                                                                                "minecraft:air"
                                                                        )
                                                                }
                                                        )
                                                )
                                                stats.blocks += 1

                if "block_entities" in chunk:
                        remove = []
                        for index, block_entity in enumerate(chunk["block_entities"]):
                                if self._is_mod(block_entity.get("id", "")):
                                        remove.append(index)
                                else:
                                        if self.clean_items(block_entity):
                                                stats.items += 1
                                        stats.attachments += self.strip_attachments(
                                                block_entity
                                        )
                        for index in reversed(remove):
                                del chunk["block_entities"][index]
                                stats.block_entities += 1

                if "entities" in chunk:
                        remove = []
                        for index, entity in enumerate(chunk["entities"]):
                                if self._is_mod(entity.get("id", "")):
                                        remove.append(index)
                                else:
                                        if self.clean_items(entity):
                                                stats.items += 1
                                        stats.attachments += self.strip_attachments(
                                                entity
                                        )
                        for index in reversed(remove):
                                del chunk["entities"][index]
                                stats.entities += 1

                stats.attachments += self.strip_attachments(chunk)

                return stats

        def clean_level_dat(self, world: Path, *, dry: bool = False) -> int:
                level_path = world / "level.dat"
                if not level_path.exists():
                        print("  level.dat not found, skipping.")
                        return 0

                data = read_nbt(level_path)
                player = data["Data"]["Player"]
                attachments = player.get("neoforge:attachments", {})

                count = 0
                for nbt_property in list(attachments):
                        if self._has_mod_key(nbt_property):
                                del attachments[nbt_property]
                                count += 1

                if count > 0:
                        print(f"  level.dat {count} attachment(s) stripped")

                if not dry and count > 0:
                        shutil.copy2(level_path, str(level_path) + ".bak")
                        write_nbt(level_path, data)

                return count

        def clean_playerdata(
                self, world: Path, *, dry: bool = False
        ) -> tuple[int, int]:
                playerdata = world / "playerdata"
                if not playerdata.is_dir():
                        print("  playerdata/ not found, skipping.")
                        return 0, 0

                total = 0
                files = 0

                for uuid_path in sorted(playerdata.glob("*.dat")):
                        if ".bak" in uuid_path.name or "_old" in uuid_path.name:
                                continue

                        data = read_nbt(uuid_path)
                        attachments = data.get("neoforge:attachments") or {}

                        count = 0
                        for nbt_property in list(attachments):
                                if self._has_mod_key(nbt_property):
                                        del attachments[nbt_property]
                                        count += 1

                        if count > 0:
                                total += count
                                files += 1
                                print(
                                        f"  {uuid_path.name} {count} attachment(s) stripped"
                                )
                                if not dry:
                                        shutil.copy2(uuid_path, str(uuid_path) + ".bak")
                                        write_nbt(uuid_path, data)

                return total, files
