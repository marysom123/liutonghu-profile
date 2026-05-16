#!/usr/bin/env python3
"""
Automate DWG to PDF conversion:
1. Use LibreCAD GUI to open DWG and save as DXF
2. Use ezdxf + matplotlib to render DXF to PDF (vector)
3. Merge all PDFs into one multi-page document
"""

import os
import sys
import time
import subprocess
import signal

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


def run_xdotool(args):
    result = subprocess.run(["xdotool"] + args, env=env, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode


def wait_for_window(name, pid, timeout=30):
    for _ in range(timeout * 2):
        out, rc = run_xdotool(["search", "--pid", str(pid), "--name", name])
        if rc == 0 and out.strip():
            return out.strip().split("\n")[0]
        out, rc = run_xdotool(["search", "--name", name])
        if rc == 0 and out.strip():
            return out.strip().split("\n")[0]
        time.sleep(0.5)
    return None


def get_window_geometry(wid):
    out, rc = run_xdotool(["getwindowgeometry", wid])
    pos = None
    size = None
    for line in out.split("\n"):
        if "Position:" in line:
            parts = line.strip().split(":")[1].strip().split()
            xy = parts[0].split(",")
            pos = (int(xy[0]), int(xy[1]))
        if "Geometry:" in line:
            parts = line.strip().split(":")[1].strip().split("x")
            size = (int(parts[0]), int(parts[1]))
    return pos, size


def click_button(x, y):
    run_xdotool(["mousemove", str(x), str(y)])
    time.sleep(0.3)
    run_xdotool(["click", "1"])
    time.sleep(0.5)


def convert_dwg_to_dxf(dwg_path):
    """Use LibreCAD GUI to convert DWG to DXF."""
    abs_dwg = os.path.abspath(dwg_path)
    base = os.path.splitext(os.path.basename(dwg_path))[0]
    dxf_out = os.path.join(OUTPUT_DIR, base + ".dxf")

    print(f"\n--- Opening: {abs_dwg} ---")

    proc = subprocess.Popen(
        ["librecad", abs_dwg],
        env=env,
        stdout=open(f"/tmp/lc_{base}.log", "w"),
        stderr=subprocess.STDOUT,
    )

    # Wait for main window
    time.sleep(20)

    # Dismiss the "DWG support is not complete!" Information dialog if present
    for _ in range(5):
        info_wid, rc = run_xdotool(["search", "--name", "Information"])
        if rc == 0 and info_wid:
            info_wid = info_wid.split("\n")[0]
            pos, size = get_window_geometry(info_wid)
            if pos and size:
                # Click OK button (bottom center-right)
                btn_x = pos[0] + int(size[0] * 0.5)
                btn_y = pos[1] + int(size[1] * 0.87)
                print(f"Clicking OK at ({btn_x}, {btn_y})")
                click_button(btn_x, btn_y)
                time.sleep(3)
                break
        time.sleep(1)

    # Use Ctrl+Shift+S (Save As)
    run_xdotool(["key", "ctrl+shift+s"])
    time.sleep(3)

    # Find the Save As dialog
    save_wid = None
    for _ in range(10):
        out, rc = run_xdotool(["search", "--name", "Save Drawing"])
        if rc == 0 and out.strip():
            save_wid = out.strip().split("\n")[0]
            break
        out, rc = run_xdotool(["search", "--name", "Save"])
        if rc == 0 and out.strip():
            save_wid = out.strip().split("\n")[0]
            break
        time.sleep(0.5)

    print(f"Save dialog: {save_wid}")

    if save_wid:
        # Type the output path in the filename field
        run_xdotool(["key", "ctrl+a"])
        time.sleep(0.3)
        run_xdotool(["type", "--clearmodifiers", "--", dxf_out])
        time.sleep(0.5)
        run_xdotool(["key", "Return"])
        time.sleep(3)

        # Handle any confirmation dialogs (format change etc.)
        for _ in range(5):
            out, rc = run_xdotool(["search", "--name", "Warning"])
            if rc == 0 and out.strip():
                run_xdotool(["key", "Return"])
                time.sleep(1)

    time.sleep(2)

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    if os.path.exists(dxf_out):
        print(f"DXF saved: {dxf_out}")
        return dxf_out

    print(f"DXF not saved at {dxf_out}")
    return None


def render_dxf_to_pdf(dxf_path, pdf_path):
    """Render DXF file to PDF using ezdxf + matplotlib (vector output)."""
    import ezdxf
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    print(f"Rendering DXF to PDF: {dxf_path}")

    doc = ezdxf.readfile(dxf_path)

    # A1 paper size: 841mm x 594mm (landscape)
    # At 96 DPI: 841/25.4*96 = 3179 x 594/25.4*96 = 2245 pixels
    # But we want to set it in inches for matplotlib: 841/25.4 = 33.11 x 594/25.4 = 23.39
    fig_width_in = 841 / 25.4  # A1 width in inches
    fig_height_in = 594 / 25.4  # A1 height in inches

    fig = plt.figure(figsize=(fig_width_in, fig_height_in), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_aspect("equal")

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)

    # Get model space
    msp = doc.modelspace()
    Frontend(ctx, out).draw_layout(msp)

    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.margins(0.02)

    plt.savefig(pdf_path, format="pdf", bbox_inches="tight", dpi=150)
    plt.close(fig)

    print(f"PDF saved: {pdf_path}")
    return True


def merge_pdfs(pdf_files, output_path):
    """Merge multiple PDFs into one."""
    from PyPDF2 import PdfMerger

    merger = PdfMerger()
    for pdf in pdf_files:
        merger.append(pdf)

    with open(output_path, "wb") as out:
        merger.write(out)

    merger.close()
    print(f"\nMerged PDF: {output_path}")
    return True


def main():
    print("=== DWG to PDF Conversion ===\n")

    os.chdir(BASE_DIR)

    dxf_pdf_pairs = []

    for dwg_file in DWG_FILES:
        if not os.path.exists(dwg_file):
            print(f"File not found: {dwg_file}")
            continue

        base = os.path.splitext(os.path.basename(dwg_file))[0]
        dxf_path = os.path.join(OUTPUT_DIR, base + ".dxf")
        pdf_path = os.path.join(OUTPUT_DIR, base + ".pdf")

        # Convert DWG to DXF via LibreCAD
        dxf_result = convert_dwg_to_dxf(dwg_file)

        if dxf_result and os.path.exists(dxf_result):
            # Render DXF to PDF
            try:
                render_dxf_to_pdf(dxf_result, pdf_path)
                dxf_pdf_pairs.append((dxf_result, pdf_path))
                print(f"✓ {dwg_file} → {pdf_path}")
            except Exception as e:
                print(f"✗ Render failed for {dwg_file}: {e}")
        else:
            print(f"✗ DXF conversion failed for {dwg_file}")

    if dxf_pdf_pairs:
        pdf_files = [p for _, p in dxf_pdf_pairs if os.path.exists(p)]
        if len(pdf_files) >= 2:
            merged_path = os.path.join(OUTPUT_DIR, "combined_drawings.pdf")
            merge_pdfs(pdf_files, merged_path)
            print(f"\n=== Done! Merged PDF: {merged_path} ===")
        elif len(pdf_files) == 1:
            print(f"\n=== Done! Single PDF: {pdf_files[0]} ===")
    else:
        print("\n=== No PDFs were generated ===")


if __name__ == "__main__":
    main()
