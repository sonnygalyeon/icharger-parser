"""
scripts/install.py
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys


def run(cmd: list[str]):

    subprocess.check_call(cmd)


def main():

    print("=" * 60)
    print("iCharger Analyzer Installer")
    print("=" * 60)

    print("Python :", platform.python_version())
    print("OS     :", platform.system())
    print("CPU    :", platform.machine())

    if not os.path.exists("venv"):

        print("\nCreating virtual environment...")

        run([sys.executable, "-m", "venv", "venv"])

    if platform.system() == "Windows":

        pip = "venv\\Scripts\\pip.exe"

    else:

        pip = "venv/bin/pip"

    print("\nInstalling dependencies...\n")

    run([pip, "install", "--upgrade", "pip"])

    run([pip, "install", "-r", "requirements.txt"])

    print("\nDone.")


if __name__ == "__main__":

    main()