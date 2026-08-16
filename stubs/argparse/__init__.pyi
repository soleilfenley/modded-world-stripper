class Namespace:
        def __getattr__(self, _name: str) -> object: ...
        world: str
        dry_run: bool
        no_backup: bool
        no_voxy: bool

class ArgumentParser:
        def __init__(self, description: str = "") -> None: ...
        def add_argument(
                self,
                *args: str,
                action: str | None = None,
                help: str | None = None,
        ) -> None: ...
        def parse_args(self) -> Namespace: ...
