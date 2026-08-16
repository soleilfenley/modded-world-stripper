import gzip
import io
from pathlib import Path

import nbtlib


def read_nbt(path: Path) -> nbtlib.File:
        with open(path, "rb") as file:
                return nbtlib.File.parse(io.BytesIO(gzip.decompress(file.read())))


def write_nbt(path: Path, data: nbtlib.File) -> None:
        buffer = io.BytesIO()
        data.write(buffer)
        with open(path, "wb") as file:
                _ = file.write(gzip.compress(buffer.getvalue()))
