#!/usr/bin/env python3
"""Convert DWG files to PDF using LibreCAD GUI automation."""

import os
import sys
import time
import subprocess
import signal

DWG_FILES = [
    "3#基础结构图0620.dwg",
    "3#车间轻钢屋面0620_t3.dwg",
    "【勋辉】3#车间楼梯结构图250618.dwg",
    "【勋辉】3#车间结构图250620.dwg",
]

OUTPUT_DIR = "/home/user/liutonghu-profile/dwg_conversion/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DISPLAY = ":99"
XDG_RUNTIME = "/tmp/xdg_runtime"
os.makedirs(XDG_RUNTIME, exist_ok=True)
os.chmod(XDG_RUNTIME, 0o700)

env = os.environ.copy()
env["DISPLAY"] = DISPLAY
env["XDG_RUNTIME_DIR"] = XDG_RUNTIME


def xdo(cmd):
    result = subprocess.run(
        ["xdotool"] + cmd, env=env, capture_output=True, text=True
    )
    return result.stdout.strip(), result.returncode


def wait_for_window(title_partial, timeout=30):
    for _ in range(timeout * 2):
        out, rc = xdo(["search", "--name", "--onlyvisible", title_partial])
        if rc == 0 and out.strip():
            return out.strip().split("\n")[0]
        time.sleep(0.5)
    return None


def convert_dwg_to_dxf(dwg_path, dxf_path):
    """Open DWG in LibreCAD GUI and save as DXF."""
    abs_dwg = os.path.abspath(dwg_path)
    print(f"Opening: {abs_dwg}")

    proc = subprocess.Popen(
        ["librecad", abs_dwg],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for LibreCAD to open
    time.sleep(8)

    # Get the window ID
    wid, rc = xdo(["search", "--pid", str(proc.pid), "--onlyvisible", "--name", ""])
    if not wid:
        wid, rc = xdo(["search", "--name", "LibreCAD"])

    print(f"Window ID: {wid}, RC: {rc}")

    if not wid:
        print("Could not find LibreCAD window")
        proc.terminate()
        return False

    wid = wid.split("\n")[0]

    # Activate window
    xdo(["windowactivate", "--sync", wid])
    time.sleep(1)

    # File > Save As (Ctrl+Shift+S)
    xdo(["key", "--window", wid, "ctrl+shift+s"])
    time.sleep(3)

    # Look for save dialog
    dialog_wid, _ = xdo(["search", "--name", "Save Drawing As"])
    if not dialog_wid:
        dialog_wid, _ = xdo(["search", "--name", "Save"])

    print(f"Dialog window: {dialog_wid}")

    # Type the output path
    xdo(["key", "ctrl+a"])
    time.sleep(0.3)
    xdo(["type", "--", abs_dxf])
    time.sleep(0.5)
    xdo(["key", "Return"])
    time.sleep(2)

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    return os.path.exists(dxf_path)


def main():
    print("Starting DWG to PDF conversion")

    dxf_files = []

    for dwg_file in DWG_FILES:
        if not os.path.exists(dwg_file):
            print(f"File not found: {dwg_file}")
            continue

        base = os.path.splitext(os.path.basename(dwg_file))[0]
        dxf_path = os.path.join(OUTPUT_DIR, base + ".dxf")
        pdf_path = os.path.join(OUTPUT_DIR, base + ".pdf")

        print(f"\n=== Processing: {dwg_file} ===")

        if convert_dwg_to_dxf(dwg_file, dxf_path):
            print(f"DXF saved: {dxf_path}")
            dxf_files.append((dxf_path, pdf_path))
        else:
            print(f"Failed to convert: {dwg_file}")

    print(f"\nConverted {len(dxf_files)} files")
    return dxf_files


if __name__ == "__main__":
    abs_dxf = "/tmp/test.dxf"
    main()
