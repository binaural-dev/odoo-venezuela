import importlib.util
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def load_migration(version, name):
    """Load migrations/<version>/post-migration.py the same way Odoo's loader does."""
    spec = importlib.util.spec_from_file_location(
        name, MIGRATIONS / version / "post-migration.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
