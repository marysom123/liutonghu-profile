#!/usr/bin/env python3
"""
Convert DWG files to PDF:
1. Open each DWG in LibreCAD GUI
2. Dismiss the DWG warning dialog
3. Save as DXF
4. Convert DXF to PDF using librecad dxf2pdf
5. Merge all PDFs
"""

import os
import sys
import time
import subprocess
import shutil

DISPLAY = ":99"
XDG_RUNTIME = "/tmp/xdg_runtime"
os.makedirs(XDG_RUNTIME, exist_ok=True)
os.chmod(XDG_RUNTIME, 0o700)

env = os.environ.copy()
env["DISPLAY"] = DISPLAY
env["XDG_RUNTIME_DIR"] = XDG_RUNTIME

BASE_DIR = "/home/user/liutonghu-profile/dwg_conversion"
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DWG_FILES = [
    "3#基础结构图0620.dwg",
    "3#车间轻钢屋面0620_t3.dwg",
    "【勋辉】3#车间楼梯结构图250618.dwg",
    "【勋辉】3#车间结构图250620.dwg",
]

# From pixel analysis: OK button is at approximately (673, 548)
OK_BTN_X = 673
OK_BTN_Y = 548


def xdo(*args):
    result = subprocess.run(["xdotool"] + list(args), env=env, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode


def click(x, y):
    xdo("mousemove", str(x), str(y))
    time.sleep(0.2)
    xdo("click", "1")
    time.sleep(0.3)


def key(*keys):
    xdo("key", "--clearmodifiers", *keys)
    time.sleep(0.3)


def type_text(text):
    xdo("type", "--clearmodifiers", "--delay", "50", "--", text)
    time.sleep(0.5)


def find_windows(pid):
    out, rc = xdo("search", "--pid", str(pid))
    if rc == 0 and out.strip():
        return out.strip().split("\n")
    return []


def find_window_by_name(name, pid=None):
    args = ["search", "--name", name]
    if pid:
        args = ["search", "--pid", str(pid), "--name", name]
    out, rc = xdo(*args)
    if rc == 0 and out.strip():
        return out.strip().split("\n")[0]
    return None


def get_geometry(wid):
    out, rc = xdo("getwindowgeometry", wid)
    pos, size = None, None
    for line in out.split("\n"):
        if "Position:" in line:
            xy = line.split(":")[1].strip().split()[0].split(",")
            pos = (int(xy[0]), int(xy[1]))
        if "Geometry:" in line:
            wh = line.split(":")[1].strip().split("x")
            size = (int(wh[0]), int(wh[1]))
    return pos, size


def convert_dwg_to_dxf(dwg_file):
    """Open DWG in LibreCAD, dismiss warning, save as DXF."""
    abs_dwg = os.path.abspath(os.path.join(BASE_DIR, dwg_file))
    base = os.path.splitext(os.path.basename(dwg_file))[0]
    dxf_out = os.path.join(OUTPUT_DIR, base + ".dxf")

    print(f"\n{'='*60}")
    print(f"Processing: {dwg_file}")
    print(f"Output DXF: {dxf_out}")

    log_file = f"/tmp/lc_{base[:20]}.log"
    proc = subprocess.Popen(
        ["librecad", abs_dwg],
        env=env,
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
    )

    print(f"LibreCAD PID: {proc.pid}")
    print("Waiting for DWG to load (20s)...")
    time.sleep(20)

    # Check if process is still running
    if proc.poll() is not None:
        print("LibreCAD exited early!")
        return None

    # Click OK on the Information dialog
    print(f"Clicking OK button at ({OK_BTN_X}, {OK_BTN_Y})")
    click(OK_BTN_X, OK_BTN_Y)
    time.sleep(5)

    # Verify the drawing is loaded
    windows = find_windows(proc.pid)
    titles = []
    for wid in windows:
        out, _ = xdo("getwindowname", wid)
        titles.append(out)
    print(f"Windows: {titles}")

    dwg_loaded = any(base[:10] in t or ".dwg" in t for t in titles)
    if not dwg_loaded:
        print("WARNING: DWG may not have loaded properly")

    # Save As DXF using Ctrl+Shift+S
    print("Saving as DXF (Ctrl+Shift+S)...")
    key("ctrl+shift+s")
    time.sleep(3)

    # Type the full DXF path in the save dialog
    # Qt file dialog: type path and press Enter
    print(f"Typing DXF path: {dxf_out}")
    type_text(dxf_out)
    time.sleep(1)
    key("Return")
    time.sleep(3)

    # Handle any format warning dialog
    for _ in range(5):
        warn_wid = find_window_by_name("Warning")
        if warn_wid:
            print("Dismissing format warning dialog...")
            key("Return")
            time.sleep(1)
            break
        time.sleep(0.5)

    # Handle any save confirmation dialog
    for _ in range(5):
        warn_wid = find_window_by_name("Save Drawing")
        if warn_wid:
            key("Return")
            time.sleep(1)
            break
        time.sleep(0.5)

    time.sleep(3)

    # Check if DXF was saved
    if os.path.exists(dxf_out):
        size = os.path.getsize(dxf_out)
        print(f"DXF saved! Size: {size} bytes")
    else:
        print(f"DXF not found at {dxf_out}")

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    return dxf_out if os.path.exists(dxf_out) else None


def dxf_to_pdf(dxf_path, pdf_path):
    """Convert DXF to PDF using librecad dxf2pdf (A1 landscape, vector)."""
    print(f"Converting DXF to PDF: {dxf_path}")

    # A1 landscape: 841mm x 594mm
    result = subprocess.run(
        [
            "librecad", "dxf2pdf",
            "-a",          # Auto fit
            "-c",          # Center
            "-k",          # Grayscale
            "-m",          # Monochrome (black/white)
            "-p", "841x594",  # A1 landscape in mm
            "-r", "300",   # 300 DPI
            "-f", "5,5,5,5",  # 5mm margins
            "-o", pdf_path,
            dxf_path,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode == 0 and os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        print(f"PDF created! Size: {size} bytes")
        return True
    else:
        print(f"dxf2pdf failed: {result.stderr}")
        return False


def merge_pdfs(pdf_files, output_path):
    """Merge multiple PDFs into one multi-page document."""
    from PyPDF2 import PdfMerger

    print(f"\nMerging {len(pdf_files)} PDFs...")
    merger = PdfMerger()

    for pdf in pdf_files:
        if os.path.exists(pdf):
            size = os.path.getsize(pdf)
            print(f"  Adding: {os.path.basename(pdf)} ({size} bytes)")
            merger.append(pdf)
        else:
            print(f"  Skipping missing: {pdf}")

    with open(output_path, "wb") as f:
        merger.write(f)
    merger.close()

    size = os.path.getsize(output_path)
    print(f"Merged PDF: {output_path} ({size} bytes)")
    return True


def main():
    print("=== DWG to PDF Batch Conversion ===")
    print(f"Base dir: {BASE_DIR}")
    print(f"Output dir: {OUTPUT_DIR}")

    os.chdir(BASE_DIR)

    pdf_files = []
    failed = []

    for dwg_file in DWG_FILES:
        if not os.path.exists(os.path.join(BASE_DIR, dwg_file)):
            print(f"File not found: {dwg_file}")
            continue

        base = os.path.splitext(os.path.basename(dwg_file))[0]
        dxf_path = os.path.join(OUTPUT_DIR, base + ".dxf")
        pdf_path = os.path.join(OUTPUT_DIR, base + ".pdf")

        # Step 1: DWG -> DXF via LibreCAD GUI
        dxf_result = convert_dwg_to_dxf(dwg_file)

        if not dxf_result or not os.path.exists(dxf_result):
            print(f"FAILED: Could not convert {dwg_file} to DXF")
            failed.append(dwg_file)
            continue

        # Step 2: DXF -> PDF via librecad dxf2pdf
        if dxf_to_pdf(dxf_result, pdf_path):
            pdf_files.append(pdf_path)
            print(f"✓ {dwg_file}")
        else:
            print(f"✗ PDF conversion failed for {dwg_file}")
            failed.append(dwg_file)

    print(f"\n{'='*60}")
    print(f"Converted: {len(pdf_files)} / {len(DWG_FILES)} files")

    if failed:
        print(f"Failed: {failed}")

    if len(pdf_files) == 0:
        print("No PDFs generated!")
        return 1

    # Step 3: Merge all PDFs into one
    final_pdf = os.path.join(OUTPUT_DIR, "combined_drawings.pdf")
    if len(pdf_files) > 1:
        merge_pdfs(pdf_files, final_pdf)
    else:
        shutil.copy(pdf_files[0], final_pdf)
        print(f"Single PDF: {final_pdf}")

    print(f"\n=== DONE! Final PDF: {final_pdf} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
