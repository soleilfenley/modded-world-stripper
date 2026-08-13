import gzip
import struct
import zlib
from collections.abc import Iterator
from pathlib import Path


class RegionFile:
        SECTOR = 4096
        HEADER = SECTOR * 2

        def __init__(self, path: Path):
                self.path = path
                self._locations: list[tuple[int, int]] = []
                self._timestamps: list[int] = []

        def read_header(self) -> None:
                if self.path.stat().st_size < self.HEADER:
                        self._locations = [(0, 0)] * 1024
                        self._timestamps = [0] * 1024
                        return
                with open(self.path, "rb") as file:
                        locations = []
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
                with open(self.path, "rb") as file:
                        file.seek(offset * self.SECTOR)
                        length = struct.unpack(">I", file.read(4))[0]
                        comp = file.read(1)[0]
                        data = file.read(length - 1)

                if comp == 2:
                        return zlib.decompress(data)
                if comp == 1:
                        return gzip.decompress(data)
                return data

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
                location_table = bytearray(4096)
                timestamp_table = bytearray(4096)
                sector_data = bytearray()
                current_sector = 2

                for index in range(1024):
                        chunk_x, chunk_z = index % 32, index // 32
                        pos = (chunk_x, chunk_z)
                        if pos in chunks and chunks[pos] is not None:
                                compressed = zlib.compress(chunks[pos])
                                payload = (
                                        struct.pack(">I", len(compressed) + 1)
                                        + b"\x02"
                                        + compressed
                                )
                                alloc_sectors = (
                                        len(payload) + self.SECTOR - 1
                                ) // self.SECTOR
                                padded_payload = payload + b"\x00" * (
                                        alloc_sectors * self.SECTOR - len(payload)
                                )
                                struct.pack_into(
                                        ">I",
                                        location_table,
                                        index * 4,
                                        (current_sector << 8) | alloc_sectors,
                                )
                                sector_data.extend(padded_payload)
                                current_sector += alloc_sectors
                with open(self.path, "wb") as file:
                        file.write(location_table)
                        file.write(timestamp_table)
                        file.write(sector_data)
