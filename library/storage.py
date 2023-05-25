from pathlib import Path


def dir(pth: str) -> Path:
    real = Path(__file__).parent.parent / "data" / pth
    real.mkdir(parents=True, exist_ok=True)
    return real.resolve()
