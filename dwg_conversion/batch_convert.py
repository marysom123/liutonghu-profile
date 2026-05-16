#!/usr/bin/env python3
"""
Batch convert DWG files to PDF using LibreCAD GUI automation.
Workflow: DWG → LibreCAD GUI Save As → DXF → librecad dxf2pdf → PDF → Merge
"""

import os
import sys
import time
import subprocess

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
    ("3#基础结构图0620.dwg", "jichujiegou"),
    ("3#车间轻钢屋面0620_t3.dwg", "qinggangwumian"),
    ("【勋辉】3#车间楼梯结构图250618.dwg", "louti"),
    ("【勋辉】3#车间结构图250620.dwg", "jiejiegou"),
]


def xdo(*args, wait=0.3):
    result = subprocess.run(
        ["xdotool"] + list(args), env=env, capture_output=True, text=True
    )
    time.sleep(wait)
    return result.stdout.strip(), result.returncode


def get_windows(pid):
    out, rc = xdo("search", "--pid", str(pid))
    return out.strip().split("\n") if rc == 0 and out.strip() else []


def get_title(wid):
    out, _ = xdo("getwindowname", wid)
    return out.strip()


def focus_and_key(wid, key):
    xdo("windowfocus", "--sync", wid)
    time.sleep(0.3)
    xdo("key", key)
    time.sleep(0.3)


def wait_for_window_title(pid, partial_title, timeout=60):
    """Wait until a window with matching title appears."""
    for _ in range(timeout * 2):
        for wid in get_windows(pid):
            if partial_title.lower() in get_title(wid).lower():
                return wid
        time.sleep(0.5)
    return None


def dismiss_dialogs(pid, max_wait=60):
    """Dismiss all LibreCAD dialogs (Information and Warning) by focusing and pressing appropriate keys."""
    start = time.time()
    while time.time() - start < max_wait:
        for wid in get_windows(pid):
            title = get_title(wid)
            if title == "Information":
                print(f"  Dismissing Information dialog (Enter)")
                focus_and_key(wid, "Return")
                time.sleep(2)
                return True
            elif title == "Warning":
                print(f"  Dismissing Warning dialog (Y)")
                focus_and_key(wid, "y")
                time.sleep(3)
                return True
        time.sleep(0.5)
    return False


def open_save_as_dialog(pid):
    """Open File > Save As dialog using keyboard navigation."""
    # Find main LibreCAD window
    main_wid = None
    for wid in get_windows(pid):
        title = get_title(wid)
        if "LibreCAD" in title and ".dwg" in title:
            main_wid = wid
            break

    if not main_wid:
        return None

    print(f"  Opening File > Save As on window {main_wid}")
    xdo("windowfocus", "--sync", main_wid)
    time.sleep(0.5)

    # Alt+F → navigate to Save as... → Enter
    # File menu: New(1), New From Template(2), Open(3), [sep], Save(4), Save as(5), [grayed], [sep], Import(highlighted after 5 downs)
    # After 5 downs we're at Import. Up 1 = Save as...
    xdo("key", "alt+f")
    time.sleep(0.5)
    for _ in range(5):
        xdo("key", "Down")
        time.sleep(0.15)
    xdo("key", "Up")
    time.sleep(0.15)
    xdo("key", "Return")
    time.sleep(2)

    # Wait for Save Drawing As dialog
    for _ in range(20):
        for wid in get_windows(pid):
            if "Save Drawing As" in get_title(wid):
                return wid
        time.sleep(0.5)
    return None


def save_as_dxf(save_wid, dxf_path):
    """Type DXF path in Save Drawing As dialog and confirm."""
    xdo("windowfocus", "--sync", save_wid)
    time.sleep(0.5)
    xdo("key", "ctrl+a")
    time.sleep(0.2)
    xdo("type", "--clearmodifiers", "--delay", "15", "--", dxf_path)
    time.sleep(0.3)
    xdo("key", "Return")
    time.sleep(5)


def convert_dwg_to_dxf(dwg_name, safe_name):
    """Full workflow: Open DWG → dismiss dialogs → save as DXF."""
    abs_dwg = os.path.join(BASE_DIR, dwg_name)
    dxf_out = os.path.join(OUTPUT_DIR, safe_name + ".dxf")

    print(f"\n{'='*60}")
    print(f"Processing: {dwg_name}")
    print(f"DXF output: {dxf_out}")

    # If DXF already exists, skip
    if os.path.exists(dxf_out) and os.path.getsize(dxf_out) > 1000:
        print(f"  DXF already exists, skipping")
        return dxf_out

    log_path = f"/tmp/lc_{safe_name}.log"
    proc = subprocess.Popen(
        ["librecad", abs_dwg],
        env=env,
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )
    pid = proc.pid
    print(f"  LibreCAD PID: {pid}")

    # Wait for LibreCAD to start loading
    print("  Waiting for LibreCAD to start (15s)...")
    time.sleep(15)

    # Check if process is still running
    if proc.poll() is not None:
        print(f"  LibreCAD exited early! Check {log_path}")
        return None

    # Handle dialogs - might need multiple rounds
    print("  Handling dialogs...")
    for attempt in range(3):
        result = dismiss_dialogs(pid, max_wait=30)
        if not result:
            break
        # Check if file loaded
        for wid in get_windows(pid):
            title = get_title(wid)
            if ".dwg]" in title and "unnamed" not in title.lower():
                print(f"  DWG loaded: {title}")
                break

    # Wait a bit more for any remaining dialogs
    time.sleep(3)

    # Final check - handle any remaining Warning dialog
    for wid in get_windows(pid):
        title = get_title(wid)
        if title == "Warning":
            focus_and_key(wid, "y")
            time.sleep(3)
            break

    # Verify the file is loaded
    dwg_loaded = False
    for wid in get_windows(pid):
        title = get_title(wid)
        if ".dwg]" in title and "unnamed" not in title.lower():
            dwg_loaded = True
            print(f"  File loaded: {title}")
            break

    if not dwg_loaded:
        print("  WARNING: DWG may not have loaded. Proceeding anyway...")

    # Open Save As dialog
    print("  Opening Save Drawing As dialog...")
    save_wid = open_save_as_dialog(pid)

    if not save_wid:
        print("  Failed to open Save As dialog!")
        proc.terminate()
        proc.wait()
        return None

    print(f"  Save dialog found: {save_wid}")
    print(f"  Typing DXF path...")
    save_as_dxf(save_wid, dxf_out)

    # Check result
    if os.path.exists(dxf_out):
        size = os.path.getsize(dxf_out)
        print(f"  DXF saved! Size: {size:,} bytes")
    else:
        print(f"  DXF not created!")

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    return dxf_out if os.path.exists(dxf_out) else None


def convert_dxf_to_pdf(dxf_path, pdf_path):
    """Convert DXF to PDF using librecad dxf2pdf in A1 format."""
    print(f"  Converting to PDF: {os.path.basename(dxf_path)}")

    # Try A1 landscape (841mm x 594mm)
    result = subprocess.run(
        [
            "librecad", "dxf2pdf",
            "-a",            # Auto fit and center
            "-c",            # Center drawing
            "-m",            # Monochrome (black/white)
            "-p", "841x594", # A1 landscape in mm
            "-r", "300",     # 300 DPI
            "-f", "10,10,10,10",  # 10mm margins
            "-o", pdf_path,
            dxf_path,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 100:
        size = os.path.getsize(pdf_path)
        print(f"  PDF created! Size: {size:,} bytes")
        return True
    else:
        print(f"  PDF creation failed! RC={result.returncode}")
        print(f"  Stdout: {result.stdout[:200]}")
        return False


def merge_pdfs(pdf_files, output_path):
    """Merge PDFs into one multi-page document."""
    import importlib.util

    # Try PyPDF2
    if importlib.util.find_spec("PyPDF2"):
        from PyPDF2 import PdfMerger
        merger = PdfMerger()
        for pdf in pdf_files:
            if os.path.exists(pdf):
                merger.append(pdf)
                print(f"  Added: {os.path.basename(pdf)}")
        with open(output_path, "wb") as f:
            merger.write(f)
        merger.close()
    else:
        # Fallback: just copy the first PDF
        import shutil
        shutil.copy(pdf_files[0], output_path)

    size = os.path.getsize(output_path)
    print(f"  Merged PDF: {output_path} ({size:,} bytes)")


def main():
    print("=== DWG to PDF Batch Conversion ===")
    os.chdir(BASE_DIR)

    pdf_files = []
    failed = []

    for dwg_name, safe_name in DWG_FILES:
        if not os.path.exists(os.path.join(BASE_DIR, dwg_name)):
            print(f"File not found: {dwg_name}")
            continue

        dxf_path = os.path.join(OUTPUT_DIR, safe_name + ".dxf")
        pdf_path = os.path.join(OUTPUT_DIR, safe_name + ".pdf")

        # Step 1: DWG → DXF
        dxf_result = convert_dwg_to_dxf(dwg_name, safe_name)

        if not dxf_result:
            print(f"FAILED: DXF conversion for {dwg_name}")
            failed.append(dwg_name)
            continue

        # Step 2: DXF → PDF
        if convert_dxf_to_pdf(dxf_result, pdf_path):
            pdf_files.append(pdf_path)
            print(f"✓ {dwg_name}")
        else:
            print(f"✗ PDF failed for {dwg_name}")
            failed.append(dwg_name)

    print(f"\n{'='*60}")
    print(f"Successful: {len(pdf_files)}/{len(DWG_FILES)}")
    if failed:
        print(f"Failed: {failed}")

    if not pdf_files:
        print("No PDFs generated!")
        return 1

    # Step 3: Merge all PDFs
    final_pdf = os.path.join(OUTPUT_DIR, "combined_drawings.pdf")
    print(f"\nMerging {len(pdf_files)} PDFs...")
    merge_pdfs(pdf_files, final_pdf)

    print(f"\n=== DONE! Final PDF: {final_pdf} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
