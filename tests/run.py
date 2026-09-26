"""Run offline tests with an installed ComfyUI Python environment."""
import argparse
from pathlib import Path
import sys
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui-root", type=Path, help="Path to a ComfyUI checkout")
    options = parser.parse_args()
    test_dir = Path(__file__).resolve().parent
    host = options.comfyui_root
    if host is None and test_dir.parent.parent.name == "custom_nodes":
        host = test_dir.parent.parent.parent
    if host is None or not (host / "comfy_api").is_dir() or not (host / "execution.py").is_file():
        parser.error("Supply --comfyui-root pointing to a ComfyUI checkout.")
    sys.path.insert(0, str(host.resolve()))
    suite = unittest.defaultTestLoader.discover(str(test_dir), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
