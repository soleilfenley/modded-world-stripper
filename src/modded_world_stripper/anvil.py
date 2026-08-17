# anvil.py
# Derived from the "strip-mod" tool suite (Soleil Fenley, 2026).
# Original: strip-mod/anvil.py — reused and extended for the oil-injector tool.
# License: GPL-3.0

import gzip
import logging
import struct
import zlib
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

class RegionFile:
        SECTOR: int = 4096
        HEADER: int = SECTOR * 2

        def __init__(self, path: Path):
                self.path:Path = path
                self._locations: list[tuple[int, int]] = []
                self._timestamps: list[int] = []

        def read_header(self) -> None:
                if self.path.stat().st_size < self.HEADER:
                        self._locations = [(0, 0)] * 1024
                        self._timestamps = [0] * 1024
                        return
                with open(self.path, "rb") as file:
                        locations: list[tuple[int, int]] = []
                        for _ in range(1024):
                                raw = file.read(4)
                                locations.append(
                                        (
                                                (raw[0] << 16) | (raw[1] << 8) | raw[2],
                                                raw[3],
                                        )
                                )
                        timestamps = list(struct.unpack(">1024I", file.read(4096)))
                self._locations = locations
                self._timestamps = timestamps

        def read_chunk(self, chunk_x: int, chunk_z: int) -> bytes | None:
                index = chunk_x + chunk_z * 32
                offset, sectors = self._locations[index]
                if offset == 0 or sectors == 0:
                        return None
                start = offset * self.SECTOR
                size = self.path.stat().st_size
                if start + 5 > size:
                        logger.warning("chunk (%d, %d) in %s points past EOF (sector %d, size %d)", chunk_x, chunk_z, self.path.name, offset, size)
                        return None
        
                with open(self.path, "rb") as file:
                        _ = file.seek(start)
                        header = file.read(5)
                        if len(header) < 5:
                                return None
                        length = int.from_bytes(header[0:4], "big")
                        comp = header[4]
                        if length <= 1 or length - 1 > sectors * self.SECTOR:
                                logger.warning("chunk (%d, %d) in %s has bad length %d", chunk_x, chunk_z, self.path.name, length)
                                return None
                        data = file.read(length - 1)
                if len(data) < length - 1:
                        logger.warning("chunk (%d, %d) in %s truncated", chunk_x, chunk_z, self.path.name)
                        return None
                if comp & 0x80:
                        external = self.path.parent / f"c.{chunk_x}.{chunk_z}.mcc"
                        if not external.is_file():
                                return None
                        data = external.read_bytes()
                        comp &= 0x7F
                if comp == 1:
                        return gzip.decompress(data)
                if comp == 2:
                        return zlib.decompress(data)
                if comp == 3:
                        return data
                logger.warning("unsupported compression scheme %d at chunk (%d, %d) in %s", comp, chunk_x, chunk_z, self.path.name)
                return None
		
        def iterate_chunks(self) -> Iterator[tuple[int, int, bytes]]:
                for index in range(1024):
                        offset, sectors = self._locations[index]
                        if offset == 0 or sectors == 0:
                                continue
                        chunk_x, chunk_z = index % 32, index // 32
                        raw = self.read_chunk(chunk_x, chunk_z)
                        if raw is not None:
                                yield chunk_x, chunk_z, raw

        def write(self, chunks: dict[tuple[int, int], bytes]) -> None:
                location_table = bytearray(self.SECTOR)
                timestamp_table = bytearray(self.SECTOR)
                sector_data = bytearray()
                current_sector = 2

                for index in range(1024):
                        chunk_x, chunk_z = index % 32, index // 32
                        nbt_bytes = chunks.get((chunk_x, chunk_z))
                        if not nbt_bytes:
                                continue

                        compressed = zlib.compress(nbt_bytes)
                        payload = (
                                struct.pack(">I", len(compressed) + 1) + b"\x02" + compressed
                        )
                        alloc_sectors = (len(payload) + self.SECTOR - 1) // self.SECTOR
                        if alloc_sectors > 255:
                                raise ValueError(f"chunk ({chunk_x}, {chunk_z}) too large for {self.path.name}")
                        padded_payload = payload + b"\x00" * (
                                alloc_sectors * self.SECTOR - len(payload)
                        )

                        struct.pack_into(">I", location_table, index * 4, (current_sector << 8) | alloc_sectors)
                        if self._timestamps:
                                struct.pack_into(">I", timestamp_table, index * 4, self._timestamps[index])
                        sector_data.extend(padded_payload)
                        current_sector += alloc_sectors
                tmp = self.path.with_name(self.path.name + ".tmp")
                with open(tmp, "wb") as file:
                        _ = file.write(location_table)
                        _ = file.write(timestamp_table)
                        _ = file.write(sector_data)
                _ = tmp.replace(self.path)