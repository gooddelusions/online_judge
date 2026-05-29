from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config(path: Path = _CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)
