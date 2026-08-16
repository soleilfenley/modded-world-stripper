import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Self

import nbtlib

from .components import read_nbt, write_nbt

logger = logging.getLogger(__name__)


@dataclass
class ChunkStats:
        blocks: int = 0
        block_entities: int = 0
        entities: int = 0
        items: int = 0
        attachments: int = 0
        structures: int = 0

        def __add__(self, other: ChunkStats) -> ChunkStats:
                return ChunkStats(
                        blocks=self.blocks + other.blocks,
                        block_entities=self.block_entities + other.block_entities,
                        entities=self.entities + other.entities,
                        items=self.items + other.items,
                        attachments=self.attachments + other.attachments,
                        structures=self.structures + other.structures
                )

        def __iadd__(self, other: ChunkStats) -> Self:
                self.blocks += other.blocks
                self.block_entities += other.block_entities
                self.entities += other.entities
                self.items += other.items
                self.attachments += other.attachments
                self.structures += other.structures
                return self

        def __bool__(self) -> bool:
                return any(
                        (
                                self.blocks,
                                self.block_entities,
                                self.entities,
                                self.items,
                                self.attachments,
                                self.structures
                        )
                )


class Cleaner:
        _namespaces: list[str]

        def __init__(self, namespaces: str | list[str]) -> None:
                if isinstance(namespaces, str):
                        self._namespaces = [namespaces]
                else:
                        self._namespaces = list(namespaces)

        def _is_mod(self, value: str) -> bool:
                return any(
                        str(value).startswith(f"{namespace}:")
                        for namespace in self._namespaces
                )

        def _has_mod_key(self, nbt_property: str) -> bool:
                return any(
                        namespace in str(nbt_property) for namespace in self._namespaces
                )

        def clean_items(self, container: nbtlib.Compound) -> bool:
                modified = False
                for nbt_property in ("Items", "Inventory", "items", "inventory"):
                        if nbt_property not in container:
                                continue
                        items = container[nbt_property]
                        if not isinstance(items, nbtlib.List):
                                continue
                        remove: list[int] = []
                        for index, item in enumerate(items):
                                if isinstance(item, nbtlib.Compound) and self._is_mod(
                                        str(item.get("id", ""))
                                ):
                                        remove.append(index)
                                if isinstance(item, nbtlib.Compound) and "tag" in item:
                                        tag = item["tag"]
                                        if (
                                                isinstance(tag, nbtlib.Compound)
                                                and "BlockEntityTag" in tag
                                        ):
                                                block_entity_tag = tag["BlockEntityTag"]
                                                if isinstance(
                                                        block_entity_tag,
                                                        nbtlib.Compound,
                                                ):
                                                        _ = self.clean_items(
                                                                block_entity_tag
                                                        )
                        for index in reversed(remove):
                                del items[index]
                                modified = True
                return modified

        def clean_structures(self, chunk: nbtlib.Compound) -> int:
                count = 0
                structures = chunk.get("structures")
                if not isinstance(structures, nbtlib.Compound):
                        return count
                for nbt_property in ("starts", "References"):
                        section = structures.get(nbt_property)
                        if not isinstance(section, nbtlib.Compound):
                                continue
                        for structure_id in list(section):
                                if self._is_mod(str(structure_id)):
                                        del section[structure_id]
                                        count += 1
                return count
                
        def strip_attachments(self, compound: nbtlib.Compound) -> int:
                count = 0
                for nbt_property in list(compound):
                        if self._has_mod_key(nbt_property):
                                del compound[nbt_property]
                                count += 1
                return count

        def clean_chunk(self, chunk: nbtlib.Compound) -> ChunkStats:
                stats = ChunkStats()

                if "sections" in chunk:
                        sections = chunk["sections"]
                        if isinstance(sections, nbtlib.List):
                                for section in sections:
                                        if not isinstance(section, nbtlib.Compound):
                                                continue
                                        block_state = section.get("block_states")
                                        if (
                                                not isinstance(
                                                        block_state, nbtlib.Compound
                                                )
                                                or "palette" not in block_state
                                        ):
                                                continue
                                        palette = block_state["palette"]
                                        if not isinstance(palette, nbtlib.List):
                                                continue
                                        for index in range(len(palette)):
                                                entry = palette[index]
                                                if isinstance(
                                                        entry, nbtlib.Compound
                                                ) and self._is_mod(
                                                        str(entry.get("Name", ""))
                                                ):
                                                        palette[index] = (
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
                        block_entities = chunk["block_entities"]
                        if isinstance(block_entities, nbtlib.List):
                                remove_block_entities: list[int] = []
                                for index, block_entity in enumerate(block_entities):
                                        if not isinstance(
                                                block_entity, nbtlib.Compound
                                        ):
                                                continue
                                        if self._is_mod(
                                                str(block_entity.get("id", ""))
                                        ):
                                                remove_block_entities.append(index)
                                        else:
                                                if self.clean_items(block_entity):
                                                        stats.items += 1
                                                stats.attachments += (
                                                        self.strip_attachments(
                                                                block_entity
                                                        )
                                                )
                                for index in reversed(remove_block_entities):
                                        del block_entities[index]
                                        stats.block_entities += 1

                if "entities" in chunk:
                        entities = chunk["entities"]
                        if isinstance(entities, nbtlib.List):
                                remove: list[int] = []
                                for index, entity in enumerate(entities):
                                        if not isinstance(entity, nbtlib.Compound):
                                                continue
                                        if self._is_mod(str(entity.get("id", ""))):
                                                remove.append(index)
                                        else:
                                                if self.clean_items(entity):
                                                        stats.items += 1
                                                stats.attachments += (
                                                        self.strip_attachments(entity)
                                                )
                                for index in reversed(remove):
                                        del entities[index]
                                        stats.entities += 1

                stats.structures += self.clean_structures(chunk)

                stats.attachments += self.strip_attachments(chunk)

                return stats

        def clean_level_dat(self, world: Path, *, dry: bool = False) -> int:
                level_path = world / "level.dat"
                if not level_path.exists():
                        print("  level.dat not found, skipping.")
                        return 0

                data = read_nbt(level_path)
                data_compound = data["Data"]
                if not isinstance(data_compound, nbtlib.Compound):
                        return 0
                player = data_compound["Player"]
                if not isinstance(player, nbtlib.Compound):
                        return 0
                attachments = player.get("neoforge:attachments", {})
                if not isinstance(attachments, nbtlib.Compound):
                        return 0

                count = 0
                for nbt_property in list(attachments):
                        if self._has_mod_key(nbt_property):
                                del attachments[nbt_property]
                                count += 1

                if count > 0:
                        print(f"  level.dat {count} attachment(s) stripped")

                if not dry and count > 0:
                        _ = shutil.copy2(level_path, str(level_path) + ".bak")
                        write_nbt(level_path, data)

                return count

        def clean_playerdata(self, world: Path, *, dry: bool = False) -> tuple[int, int]:
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
                        attachments = data.get("neoforge:attachments")
                        if not isinstance(attachments, nbtlib.Compound):
                                continue

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
                                        _ = shutil.copy2(
                                                uuid_path, str(uuid_path) + ".bak"
                                        )
                                        write_nbt(uuid_path, data)

                return total, files