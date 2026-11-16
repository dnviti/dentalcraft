"""Perfboard layout of the LED controller (60 x 40 mm, 0.1" grid, 22 x 14 holes), with a netlist check.

Grid: x = column 0..21 (left to right), y = row 0..13 (top to bottom), seen from the component side.
Hole (x, y) is at (3.33 + 2.54 x, 3.49 + 2.54 y) mm from the top-left board corner.
The four corner holes (0,0) (21,0) (0,13) (21,13) are drilled to 3.2 mm for M3.

WIRES are tinned-copper solder trails on the solder side (they must not touch another net);
LINKS are insulated jumpers on the component side (they may cross).
The check proves that the wiring realises exactly NETS (the schematic netlist): every net connected,
no two nets shorted, no wire through a hole used by another net, no part on a keep-out hole.

Writes ../perfboard.svg and ../perfboard.png.  Run: python perfboard.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NX, NY, P = 22, 14, 2.54
BOARD_W, BOARD_H = 60.0, 40.0
OX, OY = (BOARD_W - (NX - 1) * P) / 2, (BOARD_H - (NY - 1) * P) / 2
MOUNT = [(0, 0), (21, 0), (0, 13), (21, 13)]
KEEPOUT = {(x + dx, y + dy) for (x, y) in MOUNT for dx in (-1, 0, 1) for dy in (-1, 0, 1)}

# ---------------------------------------------------------------- schematic netlist
NETS = {
    "VIN":    ["J1.+", "F1.1"],
    "VF":     ["F1.2", "D1.A"],
    "+12V":   ["D1.K", "D2.K", "C1.+", "R1.1", "U2.IN", "C2.1", "U1.8", "C4.1", "J2.+"],
    "GND":    ["J1.-", "D2.A", "C1.-", "C2.2", "U2.GND", "C3.2", "U1.4", "C4.2", "C5.-", "RV2.W", "RV2.2",
               "C6.2", "R8.2", "R10.2", "C8.2", "R13.2", "R14.2", "P.LEDK", "P.POTCCW"],
    "LED_A":  ["R1.2", "P.LEDA"],
    "+5V":    ["U2.OUT", "C3.1", "J3.+", "R2.1"],
    "POT_TOP": ["R2.2", "P.POTCW"],
    "WIPER":  ["P.WIPER", "R3.1"],
    "VSET":   ["R3.2", "C5.+", "U1.3"],
    "SENS":   ["J3.S", "R4.1", "R5.1"],
    "RLM":    ["R4.2", "RV2.1"],
    "SF":     ["R5.2", "C6.1", "P.AUTO"],
    "MODE":   ["P.COM", "R6.1"],
    "INV_A":  ["R6.2", "C7.1", "U1.2"],
    "VC":     ["U1.1", "C7.2", "R7.1", "R9.1"],
    "MFB":    ["R7.2", "R8.1", "P.MAN"],
    "VCMD":   ["R9.2", "R10.1", "C8.1", "U1.5"],
    "INV_B":  ["U1.6", "C9.1", "R11.1"],
    "OUT_B":  ["U1.7", "C9.2", "R12.1"],
    "GATE":   ["R12.2", "R13.1", "Q1.G"],
    "LED_K":  ["Q1.D", "J2.K"],
    "SENSE":  ["Q1.S", "R14.1", "R11.2"],
}

# ---------------------------------------------------------------- parts
# kind: 'r' resistor lying, 'rs' resistor standing, 'c' ceramic, 'cf' film, 'ce' electrolytic, 'd' diode,
# 'dip8', 'to92', 'to220', 'term' screw terminal, 'trim' 3296W, 'pad' wire pad, 'ptc'
PARTS = {}


def part(ref, kind, value, pins, body=None):
    PARTS[ref] = dict(kind=kind, value=value, pins=pins, body=body)


# Layout idea: +12V rail along row 4 and GND rail along row 5 (decoupling parts stand across them);
# U2 stands across the rails too, so +5V comes out below them; everything else lives under the rails.
# terminals: power and strip on the top edge, sensor on the left edge (wire entry towards the board edge)
part("J1", "term", "12 V in", {"-": (3, 1), "+": (5, 1)}, (2.05, -0.55, 5.95, 2.45))
part("J2", "term", "LED strip", {"+": (14, 1), "K": (16, 1)}, (13.05, -0.55, 16.95, 2.45))
part("J3", "term", "sensor", {"+": (1, 7), "S": (1, 9)}, (-0.55, 6.05, 2.45, 9.95))
# power input
part("F1", "ptc", "RXEF075", {"1": (6, 3), "2": (8, 3)}, (5.5, 2.5, 8.5, 3.5))
part("D1", "ds", "1N5819", {"A": (9, 3), "K": (9, 4)}, None)
part("C2", "c", "100n", {"1": (6, 4), "2": (6, 5)}, None)
part("U2", "to92", "78L05", {"IN": (7, 4), "GND": (7, 5), "OUT": (7, 6)}, None)
part("C3", "c", "1u", {"2": (8, 5), "1": (8, 6)}, None)
part("D2", "ds", "P6KE15A", {"K": (10, 4), "A": (10, 5)}, None)
part("C1", "ce", "100u 25V", {"+": (12, 4), "-": (12, 5)}, None)
part("R1", "rs", "4k7", {"1": (14, 3), "2": (13, 3)}, None)
part("C4", "c", "100n", {"1": (15, 4), "2": (15, 5)}, None)
# op-amp (pin 1 top left)
part("U1", "dip8", "LM358", {"1": (12, 7), "2": (12, 8), "3": (12, 9), "4": (12, 10),
                             "5": (15, 10), "6": (15, 9), "7": (15, 8), "8": (15, 7)})
# current command and regulator (right)
part("R9", "r", "47k", {"1": (11, 7), "2": (11, 11)}, None)
part("C8", "c", "100n", {"1": (14, 11), "2": (14, 12)}, None)
part("R10", "rs", "1k", {"1": (15, 11), "2": (15, 12)}, None)
part("C9", "c", "10n", {"2": (16, 7), "1": (17, 7)}, None)
part("R12", "r", "100", {"1": (16, 8), "2": (20, 8)}, None)
part("R13", "rs", "100k", {"1": (19, 9), "2": (18, 9)}, None)
part("R11", "r", "1k", {"1": (17, 9), "2": (17, 13)}, None)
part("Q1", "to220", "IRF520N", {"G": (20, 9), "D": (20, 10), "S": (20, 11)}, (20.25, 7.95, 22.05, 12.05))
part("R14", "rs", "0R47 0.6W", {"1": (19, 11), "2": (18, 11)}, None)
# setpoint, sensor, integrator (left); positions from a placement search that minimised the jumpers
part("R2", "r", "2k2", {"1": (6, 6), "2": (2, 6)}, None)
part("R3", "r", "22k", {"1": (1, 10), "2": (5, 10)}, None)
part("R4", "rs", "2k2", {"1": (3, 9), "2": (4, 9)}, None)
part("R5", "r", "10k", {"1": (3, 12), "2": (7, 12)}, None)
part("R6", "r", "100k", {"1": (8, 13), "2": (8, 9)}, None)
part("R7", "rs", "12k", {"1": (10, 9), "2": (9, 9)}, None)
part("R8", "rs", "10k", {"1": (9, 12), "2": (10, 12)}, None)
part("C5", "ce", "10u 16V", {"+": (10, 10), "-": (10, 11)}, None)
part("C6", "c", "1u", {"1": (4, 11), "2": (5, 11)}, None)
part("C7", "cf", "1u MKT", {"1": (8, 8), "2": (10, 8)}, (7.4, 7.4, 10.6, 8.6))
part("RV2", "trim", "50k 3296W", {"1": (7, 7), "W": (8, 7), "2": (9, 7)}, (6.4, 6.4, 9.6, 7.6))
# panel wire pads: RV1 (knob), SW1 (AUTO/MAN) on the bottom edge, D3 (power LED) at the top
part("P", "pad", "panel", {"POTCW": (3, 13), "WIPER": (2, 13), "POTCCW": (11, 13), "AUTO": (4, 13), "COM": (7, 13),
                           "MAN": (10, 13), "LEDA": (12, 3), "LEDK": (4, 4)})

WIRES = []      # solder-side trails: (net, [(x,y), ...]) polyline through hole centres
LINKS = []      # component-side insulated jumpers: (net, (x,y), (x,y))


# ---------------------------------------------------------------- wiring: maze router
def pin_xy(pid):
    ref, name = pid.split(".")
    return PARTS[ref]["pins"][name]


def route_all(order):
    """Lee maze routing on the solder side, one net at a time, growing a tree from the first pin.
    Turns cost extra so trails stay straight. A pin that cannot be reached gets an insulated link.
    Returns (wires, links, trail length)."""
    import heapq
    wires, links, length = [], [], 0
    owner = {}
    for net, pins in NETS.items():
        for pid in pins:
            owner[pin_xy(pid)] = net
    for net in order:
        pins = [pin_xy(p) for p in NETS[net]]
        tree = {pins[0]}
        todo = pins[1:]
        while todo:
            # nearest remaining pin first
            todo.sort(key=lambda q: min(abs(q[0] - t[0]) + abs(q[1] - t[1]) for t in tree))
            goal = todo.pop(0)
            if goal in tree:
                continue
            best = None
            heap = [(0, t, None, (t,)) for t in sorted(tree)]
            heapq.heapify(heap)
            seen = {}
            while heap:
                cost, h, d, path = heapq.heappop(heap)
                if h == goal:
                    best = path
                    break
                if seen.get((h, d), 1e9) <= cost:
                    continue
                seen[(h, d)] = cost
                for dd in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (h[0] + dd[0], h[1] + dd[1])
                    if not (0 <= n[0] < NX and 0 <= n[1] < NY) or n in KEEPOUT:
                        continue
                    if owner.get(n, net) != net:
                        continue
                    step = 1 + (0.6 if d is not None and dd != d else 0)
                    heapq.heappush(heap, (cost + step, n, dd, path + (n,)))
            if best is None:
                t = min(sorted(tree), key=lambda q: (q[0] - goal[0]) ** 2 + (q[1] - goal[1]) ** 2)
                links.append((net, t, goal))
                tree.add(goal)
                owner[goal] = net
                continue
            # merge collinear steps into a polyline
            poly = [best[0]]
            for a, b, c in zip(best, best[1:], best[2:]):
                if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
                    poly.append(b)
            poly.append(best[-1])
            if len(best) > 1:
                wires.append((net, poly))
                length += len(best) - 1
            for h in best:
                owner[h] = net
                tree.add(h)
    return wires, links, length


def best_routing(tries=600, seed=7):
    """route the nets in many random orders; keep the one with the fewest jumpers, then the shortest."""
    import random
    rnd = random.Random(seed)
    nets = list(NETS)
    best = None
    for _ in range(tries):
        rnd.shuffle(nets)
        w, lk, ln = route_all(nets)
        score = (len(lk), ln + sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for _, a, b in lk))
        if best is None or score < best[0]:
            best = (score, w, lk, list(nets))
    return best


_score, WIRES, LINKS, ROUTE_ORDER = best_routing()


# ---------------------------------------------------------------- check
def body_holes(p):
    """holes covered by a part body (other parts must not use them)."""
    k, pins = p["kind"], list(p["pins"].values())
    if k == "dip8":
        xs = [x for x, _ in pins]
        ys = [y for _, y in pins]
        return {(x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys), max(ys) + 1)}
    if k in ("r", "d") and p["body"] is None:
        (x0, y0), (x1, y1) = pins
        if y0 == y1:
            return {(x, y0) for x in range(min(x0, x1), max(x0, x1) + 1)}
        return {(x0, y) for y in range(min(y0, y1), max(y0, y1) + 1)}
    if p["body"] is not None:
        x0, y0, x1, y1 = p["body"]
        import math
        return {(x, y) for x in range(math.ceil(x0), math.floor(x1) + 1) for y in range(math.ceil(y0), math.floor(y1) + 1)}
    return set(pins)


def segment_holes(a, b):
    (x0, y0), (x1, y1) = a, b
    if x0 != x1 and y0 != y1:
        raise ValueError(f"wire segment not orthogonal: {a} -> {b}")
    if x0 == x1:
        return [(x0, y) for y in range(min(y0, y1), max(y0, y1) + 1)]
    return [(x, y0) for x in range(min(x0, x1), max(x0, x1) + 1)]


def check():
    errors = []
    pin_net, hole_owner = {}, {}
    net_of_pin = {pin: net for net, pins in NETS.items() for pin in pins}
    all_pins = set()
    for ref, p in PARTS.items():
        for name, xy in p["pins"].items():
            pid = f"{ref}.{name}"
            all_pins.add(pid)
            if pid not in net_of_pin:
                errors.append(f"pin {pid} not in the netlist")
                continue
            if not (0 <= xy[0] < NX and 0 <= xy[1] < NY):
                errors.append(f"pin {pid} off the board at {xy}")
            if xy in KEEPOUT:
                errors.append(f"pin {pid} on a mounting keep-out hole {xy}")
            if xy in hole_owner:
                errors.append(f"hole {xy} used twice: {pid} and {hole_owner[xy]}")
            hole_owner[xy] = pid
            pin_net[xy] = net_of_pin[pid]
    for pid in net_of_pin:
        if pid not in all_pins:
            errors.append(f"netlist pin {pid} not placed")
    # bodies must not cover another part's pins
    for ref, p in PARTS.items():
        own = set(p["pins"].values())
        for h in body_holes(p) - own:
            if h in hole_owner and not hole_owner[h].startswith(ref + "."):
                errors.append(f"{ref} body covers pin {hole_owner[h]} at {h}")
    # solder-side wires
    wire_net = dict(pin_net)
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    for net, pts in WIRES:
        for a, b in zip(pts, pts[1:]):
            for h in segment_holes(a, b):
                if h in KEEPOUT:
                    errors.append(f"{net} wire through keep-out {h}")
                if h in wire_net and wire_net[h] != net:
                    errors.append(f"{net} wire touches {wire_net[h]} at {h}")
                wire_net[h] = net
            hs = segment_holes(a, b)
            for u, v in zip(hs, hs[1:]):
                union(u, v)
    for net, a, b in LINKS:
        for h in (a, b):
            if h in wire_net and wire_net[h] != net:
                errors.append(f"{net} link end on {wire_net[h]} at {h}")
            wire_net[h] = net
        union(a, b)
    # connectivity per net
    for net, pins in NETS.items():
        roots = {find(PARTS[p.split('.')[0]]["pins"][p.split('.')[1]]) for p in pins}
        if len(roots) > 1:
            groups = {}
            for p in pins:
                groups.setdefault(find(PARTS[p.split('.')[0]]["pins"][p.split('.')[1]]), []).append(p)
            errors.append(f"net {net} is split: {list(groups.values())}")
    # shorts: one connected group holding two nets
    group_net = {}
    for h, net in wire_net.items():
        r = find(h)
        if r in group_net and group_net[r] != net:
            errors.append(f"short between {group_net[r]} and {net} (at {h})")
        group_net.setdefault(r, net)
    return sorted(set(errors))


# ---------------------------------------------------------------- drawing
NET_COLOURS = {"GND": "#2b2b2b", "+12V": "#d62728", "+5V": "#ff7f0e", "VIN": "#8c564b", "VF": "#8c564b",
               "LED_K": "#9467bd", "SENSE": "#17becf"}


def hole_mm(xy):
    return OX + xy[0] * P, OY + xy[1] * P


def draw(path_svg, path_png):
    fig, ax = plt.subplots(figsize=(12, 8.4))
    ax.add_patch(FancyBboxPatch((0, 0), BOARD_W, BOARD_H, boxstyle="round,pad=0,rounding_size=1.0",
                                fc="#f3e7c9", ec="black", lw=1.2))
    for x in range(NX):
        for y in range(NY):
            cx, cy = hole_mm((x, y))
            ax.add_patch(Circle((cx, cy), 0.45, fc="white", ec="#b59a5a", lw=0.5))
    for xy in MOUNT:
        cx, cy = hole_mm(xy)
        ax.add_patch(Circle((cx, cy), 1.6, fc="white", ec="black", lw=1.0))
        ax.add_patch(Circle((cx, cy), 2.75, fc="none", ec="grey", lw=0.6, ls="--"))
        ax.text(cx, cy, "M3", ha="center", va="center", fontsize=6)
    # solder-side wires (drawn as seen through the board)
    for net, pts in WIRES:
        xs, ys = zip(*[hole_mm(p) for p in pts])
        ax.plot(xs, ys, color=NET_COLOURS.get(net, "#1f77b4"), lw=2.2, alpha=0.55, solid_capstyle="round", zorder=2)
    for net, a, b in LINKS:
        (x0, y0), (x1, y1) = hole_mm(a), hole_mm(b)
        ax.plot([x0, x1], [y0, y1], color=NET_COLOURS.get(net, "#1f77b4"), lw=1.6, ls="--", zorder=6)
    # parts
    for ref, p in PARTS.items():
        k, pins = p["kind"], p["pins"]
        pts = [hole_mm(v) for v in pins.values()]
        xs, ys = zip(*pts)
        if p["body"] is not None:
            x0, y0, x1, y1 = p["body"]
            (bx0, by0), (bx1, by1) = hole_mm((x0, y0)), hole_mm((x1, y1))
            fc = {"term": "#2ca02c", "to220": "#444444", "trim": "#1f4e9c", "ptc": "#e8b04b", "cf": "#d4af37",
                  "d": "#333333"}.get(k, "#cccccc")
            ax.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fc=fc, ec="black", lw=0.8, alpha=0.75, zorder=4))
        elif k in ("r", "d"):
            ax.plot(xs, ys, color="black", lw=0.8, zorder=4)
            mx, my = sum(xs) / 2, sum(ys) / 2
            horiz = ys[0] == ys[1]
            w, h = (6.0, 2.2) if horiz else (2.2, 6.0)
            ax.add_patch(Rectangle((mx - w / 2, my - h / 2), w, h, fc="#7fb3d5" if k == "r" else "#333333",
                                   ec="black", lw=0.8, zorder=5))
        elif k in ("rs", "ds"):
            ax.add_patch(Circle(pts[0], 1.15 if k == "rs" else 1.35, fc="#7fb3d5" if k == "rs" else "#333333",
                                ec="black", lw=0.8, zorder=5))
            ax.plot(xs, ys, color="black", lw=0.8, zorder=4)
        elif k == "ce":
            mx, my = sum(xs) / 2, sum(ys) / 2
            r = 3.15 if "100u" in p["value"] else 2.5
            ax.add_patch(Circle((mx, my), r, fc="#4a6fa5", ec="black", lw=0.8, alpha=0.8, zorder=5))
            px, py = pins["+"] if "+" in pins else (0, 0)
            ax.text(*hole_mm(pins["+"]), "+", ha="center", va="center", fontsize=8, color="white", zorder=7)
        elif k == "c":
            mx, my = sum(xs) / 2, sum(ys) / 2
            horiz = ys[0] == ys[1]
            w, h = (4.2, 1.8) if horiz else (1.8, 4.2)
            ax.add_patch(Rectangle((mx - w / 2, my - h / 2), w, h, fc="#e5a050", ec="black", lw=0.8, zorder=5))
        elif k == "dip8":
            ax.add_patch(Rectangle((min(xs) - 0.6, min(ys) - 1.2), max(xs) - min(xs) + 1.2, max(ys) - min(ys) + 2.4,
                                   fc="#222222", ec="black", lw=0.8, zorder=5))
            cx0, cy0 = hole_mm(pins["1"])
            ax.add_patch(Circle((cx0 + 1.1, cy0 - 0.2), 0.45, fc="white", zorder=6))
        elif k == "to92":
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            vert = xs[0] == xs[-1]
            w, h = (2.6, 6.6) if vert else (6.6, 2.6)
            ax.add_patch(Rectangle((mx - w / 2, my - h / 2), w, h, fc="#222222", ec="black", lw=0.8, zorder=5))
        for name, v in pins.items():
            cx, cy = hole_mm(v)
            ax.add_patch(Circle((cx, cy), 0.55, fc="#c0a060", ec="black", lw=0.6, zorder=7))
        # label
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        lab = f"{ref}\n{p['value']}" if k != "pad" else ""
        col = "white" if k in ("dip8", "to92", "to220", "term", "trim", "ce", "d") else "black"
        ax.text(mx, my, lab, ha="center", va="center", fontsize=5.2, color=col, zorder=8, fontweight="bold")
    # pin names worth showing
    pad_txt = {"LEDA": "D3 anode", "LEDK": "D3 cathode", "POTCW": "RV1 cw", "WIPER": "RV1 wiper", "POTCCW": "RV1 ccw",
               "AUTO": "SW1 AUTO", "COM": "SW1 common", "MAN": "SW1 MAN"}
    for ref in ("J1", "J2", "J3", "Q1", "U2", "P", "RV2"):
        for name, v in PARTS[ref]["pins"].items():
            cx, cy = hole_mm(v)
            if ref == "P" and v[1] == NY - 1:
                ax.text(cx, BOARD_H + 0.6, pad_txt[name], ha="center", va="top", rotation=90, fontsize=5.5,
                        color="#7a1f1f", zorder=9)
            elif ref == "P":
                ax.text(cx - 1.0, cy, pad_txt[name], ha="right", va="center", fontsize=4.8, color="#7a1f1f", zorder=9)
            else:
                ax.text(cx, cy - 0.9, name, ha="center", va="center", fontsize=4.8, color="#7a1f1f", zorder=9)
    # grid reference: columns A..V, rows 1..14
    for x in range(NX):
        ax.text(OX + x * P, -0.8, COLS[x], ha="center", va="bottom", fontsize=5, color="grey")
    for y in range(NY):
        ax.text(-0.8, OY + y * P, str(y + 1), ha="right", va="center", fontsize=5, color="grey")
    ax.set_xlim(-12, BOARD_W + 1)
    ax.set_ylim(BOARD_H + 12, -6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("LED controller perfboard, 60 x 40 mm, component side. Solid lines: solder-side tinned wire "
                 "(seen through the board); dashed: insulated jumper on top.\nM3 holes at the 4 corner grid holes: "
                 "53.34 x 33.02 mm centres; keep the grey circles clear (screw head / standoff).", fontsize=8)
    ax.text(0, BOARD_H + 10.5, "U1 pin 1 at the white dot. C1, C5: + marked. Diodes stand upright: band (K) of D1 in J5, of D2 in K5. "
            "Q1: metal tab towards the right edge. Grid: columns A-V, rows 1-14. Netlist check and wiring list: "
            "sim/perfboard.py, perfboard-wiring.md", fontsize=6.5)
    fig.tight_layout()
    fig.savefig(path_svg)
    fig.savefig(path_png, dpi=160)
    plt.close(fig)


COLS = "ABCDEFGHIJKLMNOPQRSTUV"


def hname(xy):
    return f"{COLS[xy[0]]}{xy[1] + 1}"


def wiring_list():
    """markdown: part placement and every wire/jumper, by grid reference (columns A-V, rows 1-14)."""
    out = ["# Perfboard wiring list", "",
           "Generated by `sim/perfboard.py` (do not edit by hand). Grid: columns A–V left to right, rows 1–14 top to",
           "bottom, seen from the component side; hole A1 is the top-left M3 hole. The four corner holes (A1, V1,",
           "A14, V14) are drilled to 3.2 mm. Check: every net of the schematic connected, no shorts.", "",
           "## Parts", "", "| ref | value | pins |", "|---|---|---|"]
    for ref, p in PARTS.items():
        pins = ", ".join(f"{n} {hname(v)}" for n, v in p["pins"].items())
        out.append(f"| {ref} | {p['value']} | {pins} |")
    out += ["", "## Solder-side wires (bare tinned wire, follow the holes in order)", "", "| net | path |", "|---|---|"]
    for net, pts in sorted(WIRES, key=lambda w: w[0]):
        out.append(f"| {net} | {' → '.join(hname(p) for p in pts)} |")
    out += ["", "## Insulated jumpers (component side)", "", "| net | from | to |", "|---|---|---|"]
    for net, a, b in LINKS:
        out.append(f"| {net} | {hname(a)} | {hname(b)} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    errs = check()
    for e in errs:
        print("ERROR:", e)
    draw(os.path.join(OUT, "perfboard.svg"), os.path.join(OUT, "perfboard.png"))
    with open(os.path.join(OUT, "perfboard-wiring.md"), "w") as f:
        f.write(wiring_list())
    print(f"{len(PARTS)} parts, {len(WIRES)} wires, {len(LINKS)} links, {len(errs)} errors")
    sys.exit(1 if errs else 0)
