import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    py_files = [str(p.relative_to(ROOT)) for p in ROOT.glob("*.py")]
    py_files += [str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_*.py")]
    run([sys.executable, "-m", "py_compile", *py_files])
    run([sys.executable, "test_flow.py"])
    for test in sorted((ROOT / "tests").glob("test_*.py")):
        module = f"tests.{test.stem}"
        run([sys.executable, "-m", module])
    print("all checks passed")


if __name__ == "__main__":
    main()
