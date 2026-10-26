"""LDG GEAR indicator legend for the 20 mm dual-LED Korry light guide.

Sized for a 0.4 mm nozzle: every clear stroke and every black gap is at
least 1.2 mm, so adjacent lines do not fuse. Plate is 1.2 mm thick.
Glyphs are transparent PETG through the full thickness; the mask is black PLA.
"""

from pathlib import Path

import numpy as np
import shapely.affinity as affinity
import shapely.geometry as sg
import shapely.ops as ops
import trimesh

OUT = Path(__file__).with_name("LDG_GEAR_indicator.3mf")

PLATE = 18.0
RADIUS = 0.9
THICK = 1.2
# Center black bar. Light-guide wall is 1.0 mm; keep this wider than the nozzle.
SPLIT = 0.8
# Light-guide pocket is 16.2 mm square and 3.5 mm deep. The ledge and the
# center wall are both 1.0 mm thick.
WALL_H = 3.0
WALL_T = 1.0
WALL_OUTER = 16.16  # 0.02 mm clearance per side inside the 16.2 mm hole
WALL_CENTER = 1.0
# Three 0.42 mm lines at 0.2 mm layers come out about 1.17 mm wide.
STROKE = 1.1
# Diagonals are drawn along their length by the slicer, so two lines hold up.
DIAG = 0.85
GAP = 0.75
MIN_FEATURE = 0.8
RIM = 0.75


def rounded_rect(size, radius):
    half = size / 2 - radius
    return sg.box(-half, -half, half, half).buffer(radius, resolution=16, join_style=1)


def _box(x0, y0, x1, y1):
    return sg.box(x0, y0, x1, y1)


def _band(p0, p1, width):
    """Straight stroke with flat ends, no round cap that fattens a joint."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = (dx * dx + dy * dy) ** 0.5
    px, py = -dy / length * width / 2, dx / length * width / 2
    return sg.Polygon(
        [(x0 + px, y0 + py), (x1 + px, y1 + py), (x1 - px, y1 - py), (x0 - px, y0 - py)]
    )


def block_unlk(stroke=STROKE, gap=GAP, height=5.4):
    """Block UNLK on a 0.4 mm nozzle grid.

    Strokes are about three extrusion lines wide and every gap between
    letters is at least two lines, so the slicer lays solid lines instead
    of thin gap fill. Diagonals run corner to corner across the full
    height so the black wedges in N and K stay as wide as possible.
    """
    s = stroke
    letters = []
    x = 0.0

    u_w = s * 2 + 0.85
    letters.append(
        ops.unary_union(
            [
                _box(x, 0, x + s, height),
                _box(x + u_w - s, 0, x + u_w, height),
                _box(x, 0, x + u_w, s),
            ]
        )
    )
    x += u_w + gap

    n_w = s * 2 + 1.45
    bay = _box(x + s, 0, x + n_w - s, height)
    letters.append(
        ops.unary_union(
            [
                _box(x, 0, x + s, height),
                _box(x + n_w - s, 0, x + n_w, height),
                _band((x + s * 0.5, height), (x + n_w - s * 0.5, 0), DIAG).intersection(bay),
            ]
        )
    )
    x += n_w + gap

    l_w = s + 1.15
    letters.append(ops.unary_union([_box(x, 0, x + s, height), _box(x, 0, x + l_w, s)]))
    x += l_w + gap

    # Both arms leave the end of a short stub at mid height. Every corner is
    # then 90 or about 120 degrees; an arm that meets the stem directly makes
    # a ~30 degree crotch that rounding fills solid.
    k_w = s + 2.05
    stub = 0.65
    node = (x + s + stub, height / 2)
    arms = _box(x + s, 0, x + k_w, height)
    tip_x = x + k_w - DIAG * 0.55
    letters.append(
        ops.unary_union(
            [
                _box(x, 0, x + s, height),
                _box(x + s - 0.1, height / 2 - DIAG / 2, node[0], height / 2 + DIAG / 2),
                _band(node, (tip_x, height + 0.3), DIAG).intersection(arms),
                _band(node, (tip_x, -0.3), DIAG).intersection(arms),
            ]
        )
    )

    geom = ops.unary_union(letters).buffer(0)
    minx, miny, maxx, maxy = geom.bounds
    return affinity.translate(geom, xoff=-(minx + maxx) / 2, yoff=-(miny + maxy) / 2)


def printable(geom, r=0.15):
    """Round corners only. A larger radius fills the gaps between letters."""
    return geom.buffer(r, join_style=1).buffer(-r, join_style=1)


def hollow_down_triangle(width, height, stroke):
    outer = sg.Polygon([(-width / 2, height / 2), (width / 2, height / 2), (0, -height / 2)])
    inner = outer.buffer(-stroke, join_style=2, mitre_limit=2.0)
    return outer.difference(inner)


def extrude(poly, z0, z1):
    parts = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
    meshes = []
    for part in parts:
        if part.is_empty or part.area < 1e-4:
            continue
        mesh = trimesh.creation.extrude_polygon(part, height=z1 - z0)
        mesh.apply_translation((0, 0, z0))
        meshes.append(mesh)
    return trimesh.util.concatenate(meshes)


def min_opening(poly):
    """Smallest gap: largest r where eroding by r still matches the piece count."""
    parts = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
    holes = []
    for part in parts:
        for ring in part.interiors:
            holes.append(sg.Polygon(ring))
    if not holes:
        return None
    region = ops.unary_union(holes)
    lo, hi = 0.0, 3.0
    for _ in range(18):
        mid = (lo + hi) / 2
        if region.buffer(-mid).is_empty:
            hi = mid
        else:
            lo = mid
    return lo * 2


def light_window():
    """Lit area inside the back walls. Glyphs outside this get no light."""
    opening = WALL_OUTER / 2 - WALL_T - 0.15
    window = sg.box(-opening, -opening, opening, opening)
    return window.difference(sg.box(-PLATE, -SPLIT, PLATE, SPLIT))


def legend_meshes(glyphs, thick):
    glyphs = printable(glyphs.intersection(light_window()).buffer(0))
    plate = rounded_rect(PLATE, RADIUS)
    black_poly = plate.difference(glyphs)
    half = WALL_OUTER / 2
    frame = sg.box(-half, -half, half, half).difference(
        sg.box(-half + WALL_T, -half + WALL_T, half - WALL_T, half - WALL_T)
    )
    rib = sg.box(-half + WALL_T, -WALL_CENTER / 2, half - WALL_T, WALL_CENTER / 2)
    walls = ops.unary_union([frame, rib])
    black = trimesh.util.concatenate(
        [
            extrude(black_poly, WALL_H, WALL_H + thick),
            extrude(walls, 0.0, WALL_H),
        ]
    )
    clear = extrude(glyphs, WALL_H, WALL_H + thick)
    for mesh in (black, clear):
        mesh.merge_vertices()
        mesh.fix_normals()
        if not mesh.is_volume:
            raise RuntimeError("legend mesh is not a closed volume")
    return glyphs, black, clear


def _stem(x, s, h):
    return _box(x, 0, x + s, h)


def letter_d(x, s, h, counter=0.85):
    w = s * 2 + counter
    return ops.unary_union(
        [_stem(x, s, h), _box(x, h - s, x + w, h), _box(x, 0, x + w, s), _box(x + w - s, s * 0.15, x + w, h - s * 0.15)]
    ), w


def letter_e(x, s, h, arm=1.05):
    w = s + arm
    mid = (h - s) / 2
    return ops.unary_union([_stem(x, s, h), _box(x, h - s, x + w, h), _box(x, mid, x + w, mid + s), _box(x, 0, x + w, s)]), w


def letter_c(x, s, h, arm=1.05):
    w = s + arm
    return ops.unary_union([_stem(x, s, h), _box(x, h - s, x + w, h), _box(x, 0, x + w, s)]), w


def letter_h(x, s, h, counter=0.9):
    w = s * 2 + counter
    return ops.unary_union([_stem(x, s, h), _stem(x + w - s, s, h), _box(x, (h - s) / 2, x + w, (h + s) / 2)]), w


def letter_o(x, s, h, counter=0.9):
    w = s * 2 + counter
    return ops.unary_union(
        [_stem(x, s, h), _stem(x + w - s, s, h), _box(x, h - s, x + w, h), _box(x, 0, x + w, s)]
    ), w


def letter_t(x, s, h, arm=0.85):
    w = s + arm * 2
    return ops.unary_union([_box(x, h - s, x + w, h), _stem(x + arm, s, h)]), w


def letter_n(x, s, h, mid=1.2, diag=0.85):
    w = s * 2 + mid
    bay = _box(x + s, 0, x + w - s, h)
    return ops.unary_union(
        [
            _stem(x, s, h),
            _stem(x + w - s, s, h),
            _band((x + s * 0.45, h), (x + w - s * 0.45, 0), diag).intersection(bay),
        ]
    ), w


def letter_l(x, s, h, foot=1.15):
    w = s + foot
    return ops.unary_union([_stem(x, s, h), _box(x, 0, x + w, s)]), w


def word(spec, s, h, gap):
    """spec is a list of (builder, kwargs). Returns a centered polygon."""
    parts = []
    x = 0.0
    for builder, kwargs in spec:
        geom, w = builder(x, s, h, **kwargs)
        parts.append(geom)
        x += w + gap
    geom = ops.unary_union(parts).buffer(0)
    minx, miny, maxx, maxy = geom.bounds
    return affinity.translate(geom, xoff=-(minx + maxx) / 2, yoff=-(miny + maxy) / 2)


def on_box(width=12.2, height=5.4, stroke=0.7):
    """Thin box. ON overlaps the top and bottom bars so the print has no gap."""
    outer = sg.box(-width / 2, -height / 2, width / 2, height / 2)
    inner = sg.box(-width / 2 + stroke, -height / 2 + stroke, width / 2 - stroke, height / 2 - stroke)
    # Letters run 0.25 mm into the frame, so the joint is solid instead of a slit.
    on = word(
        [(letter_o, {"counter": 1.55}), (letter_n, {"mid": 1.75, "diag": 1.0})],
        s=1.05,
        h=height - 2 * stroke + 0.5,
        gap=0.95,
    )
    return ops.unary_union([outer.difference(inner), on])


def glyphs_for(name):
    if name == "LDG_GEAR":
        upper = affinity.translate(block_unlk(), yoff=4.15)
        tri = affinity.translate(hollow_down_triangle(width=9.2, height=4.8, stroke=1.35), yoff=-4.05)
        return ops.unary_union([upper, tri])
    if name == "AUTO_BRK":
        decel = word(
            [
                (letter_d, {"counter": 0.8}),
                (letter_e, {"arm": 1.0}),
                (letter_c, {"arm": 1.0}),
                (letter_e, {"arm": 1.0}),
                (letter_l, {"foot": 1.05}),
            ],
            s=0.95,
            h=4.7,
            gap=0.72,
        )
        return ops.unary_union(
            [affinity.translate(decel, yoff=4.05), affinity.translate(on_box(), yoff=-3.9)]
        )
    if name == "BRK_FAN":
        hot = word(
            [(letter_h, {"counter": 0.95}), (letter_o, {"counter": 0.95}), (letter_t, {"arm": 0.9})],
            s=1.05,
            h=4.8,
            gap=0.85,
        )
        return ops.unary_union(
            [affinity.translate(hot, yoff=4.05), affinity.translate(on_box(), yoff=-3.9)]
        )
    if name == "TERR_ON_ND":
        return affinity.translate(on_box(), yoff=-3.9)
    raise KeyError(name)


NAMES = ("LDG_GEAR", "AUTO_BRK", "BRK_FAN", "TERR_ON_ND")


def main(thick=0.6, out=None):
    out = out or Path(__file__).with_name("korry_legends_0.6mm.3mf")
    scene = trimesh.Scene()
    pitch = PLATE + 8.0
    for i, name in enumerate(NAMES):
        glyphs, black, clear = legend_meshes(glyphs_for(name), thick)
        black.visual.face_colors = [20, 20, 20, 255]
        clear.visual.face_colors = [180, 220, 235, 110]
        shift = np.eye(4)
        shift[0, 3] = i * pitch
        scene.add_geometry(black, geom_name=f"{name}_Black", node_name=f"{name}_Black", transform=shift)
        scene.add_geometry(clear, geom_name=f"{name}_Clear", node_name=f"{name}_Clear", transform=shift)
        print(f"{name} glyphs x {glyphs.bounds[0]:.2f}..{glyphs.bounds[2]:.2f} y {glyphs.bounds[1]:.2f}..{glyphs.bounds[3]:.2f}")
    out.write_bytes(scene.export(file_type="3mf"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
