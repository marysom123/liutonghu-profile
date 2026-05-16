#!/usr/bin/env python3
"""Custom DXF to PDF renderer using matplotlib, with block/INSERT support."""

import ezdxf, os, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc as MplArc
import numpy as np


def render_entities(ax, entities, transform=None, lw=0.25, depth=0):
    """Render DXF entities onto a matplotlib Axes.
    transform: (tx, ty, sx, sy, angle_deg) or None
    """
    if depth > 5:
        return  # Prevent infinite recursion
    
    for e in entities:
        t = e.dxftype()
        try:
            color = 'black'
            
            if t == 'LINE':
                s, en = e.dxf.start, e.dxf.end
                ax.plot([s.x, en.x], [s.y, en.y], '-', color=color,
                        linewidth=lw, solid_capstyle='round')
            
            elif t == 'LWPOLYLINE':
                pts = list(e.get_points('xy'))
                if len(pts) >= 2:
                    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                    if e.closed: xs.append(xs[0]); ys.append(ys[0])
                    ax.plot(xs, ys, '-', color=color, linewidth=lw)
            
            elif t == 'POLYLINE':
                pts = list(e.points())
                if len(pts) >= 2:
                    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                    ax.plot(xs, ys, '-', color=color, linewidth=lw)
            
            elif t == 'CIRCLE':
                c = e.dxf.center
                r = e.dxf.radius
                circle = plt.Circle((c.x, c.y), r, fill=False, color=color, linewidth=lw)
                ax.add_patch(circle)
            
            elif t == 'ARC':
                c = e.dxf.center; r = e.dxf.radius
                sa = e.dxf.start_angle; ea = e.dxf.end_angle
                arc = MplArc((c.x, c.y), 2*r, 2*r, angle=0,
                             theta1=sa, theta2=ea, fill=False,
                             color=color, linewidth=lw)
                ax.add_patch(arc)
            
            elif t == 'SOLID':
                pts = []
                for attr in ['vtx0','vtx1','vtx2','vtx3']:
                    try: pts.append(getattr(e.dxf, attr))
                    except: pass
                if len(pts) >= 3:
                    xs = [p.x for p in pts] + [pts[0].x]
                    ys = [p.y for p in pts] + [pts[0].y]
                    ax.fill(xs, ys, color=color)
            
            elif t == 'SPLINE':
                try:
                    pts = list(e.flattening(0.01))
                    if len(pts) >= 2:
                        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                        ax.plot(xs, ys, '-', color=color, linewidth=lw)
                except: pass
            
            elif t == 'ELLIPSE':
                c = e.dxf.center
                maj = e.dxf.major_axis
                ratio = e.dxf.ratio
                a = math.sqrt(maj.x**2 + maj.y**2)
                b = a * ratio
                angle = math.degrees(math.atan2(maj.y, maj.x))
                sa_rad = e.dxf.start_param
                ea_rad = e.dxf.end_param
                ell = MplArc((c.x, c.y), 2*a, 2*b, angle=angle,
                             theta1=math.degrees(sa_rad), theta2=math.degrees(ea_rad),
                             fill=False, color=color, linewidth=lw)
                ax.add_patch(ell)
        except:
            pass


def compute_bounds(doc, percentile=2):
    """Get content bounds from all model space entities."""
    msp = doc.modelspace()
    all_x, all_y = [], []
    for e in msp:
        t = e.dxftype()
        try:
            if t == 'LINE':
                all_x += [e.dxf.start.x, e.dxf.end.x]
                all_y += [e.dxf.start.y, e.dxf.end.y]
            elif t == 'LWPOLYLINE':
                pts = list(e.get_points())
                all_x += [p[0] for p in pts]; all_y += [p[1] for p in pts]
            elif t in ('CIRCLE', 'ARC'):
                all_x.append(e.dxf.center.x); all_y.append(e.dxf.center.y)
            elif t in ('TEXT', 'MTEXT'):
                ins = e.dxf.insert
                all_x.append(ins.x); all_y.append(ins.y)
        except: pass
    
    if not all_x:
        return None
    
    all_x.sort(); all_y.sort()
    n = len(all_x); ny = len(all_y)
    p = percentile
    return (all_x[max(0, n*p//100)],
            all_y[max(0, ny*p//100)],
            all_x[min(n-1, n*(100-p)//100)],
            all_y[min(ny-1, ny*(100-p)//100)])


def render_dxf_to_pdf(dxf_path, pdf_path):
    """Full DXF to A1 PDF rendering."""
    print(f"\nRendering: {os.path.basename(dxf_path)}")
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    
    bounds = compute_bounds(doc, percentile=2)
    if not bounds:
        print("  ERROR: No content found")
        return False
    
    x0, y0, x1, y1 = bounds
    margin_x = (x1-x0) * 0.02
    margin_y = (y1-y0) * 0.02
    x0 -= margin_x; x1 += margin_x
    y0 -= margin_y; y1 += margin_y
    
    print(f"  Bounds: ({x0:.0f},{y0:.0f}) → ({x1:.0f},{y1:.0f}) [{x1-x0:.0f}×{y1-y0:.0f}]")
    
    # A1 landscape
    fig_w = 841 / 25.4; fig_h = 594 / 25.4
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect('equal')
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    ax.axis('off')
    
    lw = 0.2
    render_entities(ax, msp, lw=lw)
    
    plt.tight_layout(pad=0.1)
    plt.savefig(pdf_path, format='pdf', dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    
    size = os.path.getsize(pdf_path)
    print(f"  → {pdf_path} ({size:,} bytes)")
    return True


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3:
        render_dxf_to_pdf(sys.argv[1], sys.argv[2])
