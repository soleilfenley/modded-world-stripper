import shutil
import sys

from .console import enable_ansi


class ProgressBar:
        total: int
        current: int
        _active: bool
        _tty: bool
        _prefix: str

        def __init__(self, total: int, prefix: str) -> None:
                self.total = total
                self.current = 0
                self._active = False
                self._tty = sys.stdout.isatty()
                self._prefix = prefix
                if self._tty:
                        enable_ansi()

        def advance(self, label: str) -> None:
                self.current += 1
                self._render(label)

        def fail (self) -> None:
                self._close()
        
        def finish(self) -> None:
                self._close()

        def _render(self, label: str) -> None:
                frac = self.current / self.total if self.total else 1.0
                counter = f"{self.current}/{self.total}"

                if not self._tty:
                        _ = sys.stdout.write(f"  [{counter}] {label}\n")
                        _ = sys.stdout.flush()
                        return

                columns = shutil.get_terminal_size(fallback=(80, 24)).columns
                width = max(10, min(40, columns - len(counter) - 16))

                filled = int(width * frac)
                bar = "#" * filled + "-" * (width - filled)

                line1 = self._truncate(f"  {self._prefix} {label}", columns)
                line2 = self._truncate(f"  [{bar}] {int(frac * 100):3d}%  ({counter})", columns)

                prefix = "\r\x1b[1A" if self._active else ""
                self._active = True
                _ = sys.stdout.write(f"{prefix}\x1b[2K{line1}\n\x1b[2K{line2}")
                _ = sys.stdout.flush()

        @staticmethod
        def _truncate(text: str, columns: int) -> str:
                limit = columns - 1
                if len(text) <= limit:
                        return text
                return text[: max(0, limit - 1)] + "…"
        
        def _close(self) -> None:
                if self._active:
                        _ = sys.stdout.write("\n")
                        _ = sys.stdout.flush()
                        self._active = False