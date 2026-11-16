"""All driving parameters of the scan enclosure, in millimetres and degrees.

Hardware lives in profiles (SCANNERS, TURNTABLES); the pose, the enclosure, the
printer and the fasteners are separate groups. `load()` merges the selected
profiles with the groups into one flat namespace that every builder reads.
Confidence notes: H = high, M = medium, L = low (measure before printing).
"""
import math
from types import SimpleNamespace

SCANNERS = {
    "mini2": dict(
        label="Revopoint MINI 2",
        body_w=132.0,          # H  long axis, mounted horizontal (along world X)
        body_h=53.0,           # H  front face height (the 132x53 face carries the optics)
        body_d=36.0,           # H  depth along the line of sight
        scanner_mass_g=175,    # H
        rear_clear=40.0,       # H  free space behind the rear face for the straight USB-C plug
        optic_off_t=0.0,       # L  optical centre offset from the front-face centre, along body "up"
        fov_h_deg=35.5,        # L  view cone, horizontal (along the 132 mm axis)
        fov_v_deg=29.7,        # L  view cone, vertical
        mount_disc_d=35.0,     # L  Quick Mount Kit disc diameter (1/4"-20 female thread)
        mount_stack=40.0,      # L  scanner underside to disc bottom
        mount_off_s=0.0,       # L  disc centre offset from the body depth-centre, + = towards the rear
        mount_off_x=0.0,       # L  disc centre offset along the 132 mm axis
        end_guide_overlap=10.0,  # how far the cradle side plates reach up the body end faces
    ),
}

TURNTABLES = {
    "revopoint_a230_ii": dict(
        label="Revopoint Dual-axis Turntable A230-II",
        platter_d=200.0,       # H
        platter_t=10.0,        # L  platter thickness, used for clearance only
        tt_mass_g=771,
        height=82.0,           # H  total height at 0 deg
        base_shape="round",    # M  "round" (locating arcs) or "rect" (corner stops)
        base_d=200.0,          # M  196-200 measured across; round base diameter
        base_l=200.0,          # rect only: size along the tilt axis (X)
        base_w=200.0,          # rect only: size across the tilt axis (Y)
        tilt_axis_h=34.7,      # M (+-1.5) tilt axis above the base bottom
        platter_above_axis=47.0,  # M platter top above the tilt axis at 0 deg
        tilt_max=30.0,         # H
        jack_side=+1,          # 12 V jack end face on +X (buttons on -X)
        jack_h=8.0,            # M  jack centre above the base bottom
    ),
}

POSE = dict(
    target_above_platter=15.0,  # T: aim point above the platter centre at 0 deg
    distance=190.0,             # T to scanner front face, along the optical axis
    elevation=40.0,             # line of sight above horizontal
    dist_adjust=15.0,           # +- slide along the line of sight (slotted cradle)
    elev_min=30.0, elev_max=50.0,
    elev_ticks=5.0,             # tick marks on the cheeks every N degrees
)

ENCLOSURE = dict(
    wall_t=3.0,            # panel skin
    flange_t=4.0,          # panel edge flanges (also the ribs)
    flange_d=11.0,         # flange depth, inward from the skin
    base_t=8.5,            # base plate: insert hole 6.7 + 1.5 floor + margin
    side_clear=17.0,       # platter rim to side-wall skin, in X
    front_margin=20.0,     # turntable base edge to the open front edge
    back_clear=10.0,       # tower/scanner to back-wall flanges
    roof_clear=12.0,       # highest scanner point to the roof skin (roof ribs are 8)
    model_d=100.0,         # L  dental model envelope diameter (turns with the platter)
    model_h=60.0,          #    dental model height
    min_clear=10.0,        # required clearance, platter+model to every part
    loc_h=5.0, loc_w=4.0, loc_span_deg=30.0,  # turntable locating arcs
    fit=0.3,               # locating fit per side
    key_w=20.0, key_l=5.0, key_fit=0.2,       # base seam keys
    seam_rib_h=13.0,       # base seam ribs, height above the plate
    seam_rib_t=7.5,        # rear (clearance) seam rib
    seam_rib_t_insert=9.0,  # front (insert) seam rib: insert hole + floor
    base_seam_y=125.0,     # base split, behind the platter sweep
    side_split_y=72.0,     # side-wall and roof split (Y)
    split_z=156.0,         # side-wall and back-wall split (Z)
    tongue_t=1.0, tongue_l=3.0, groove_fit=0.15,
    jack_notch_w=30.0, jack_notch_h=35.0,     # DC jack pass-through in the side wall
    usb_slot_w=26.0, usb_slot_h=60.0,         # USB-C pass-through in the back wall
    cheek_t=7.0, cheek_margin=8.0, cheek_foot_w=20.0, cheek_foot_t=8.0,
    cheek_gusset_t=6.0, cheek_gusset_h=45.0,
    rib_inset=3.0,         # ribs, gussets and feet stop this far inside their plate's outline
    cradle_side_t=8.5,     # cradle side plates (guides + insert depth 6.7 + floor)
    cradle_plate_under=5.0,  # plate thickness under the disc channel
    channel_depth=3.0,     # disc locating channel depth
    guide_clear=0.5,       # scanner end face to guide plate, per side
    cradle_margin=8.0,     # plate length beyond the channel ends
    bolt_ds=20.0,          # cradle bolts at channel centre +- bolt_ds along the line of sight
    bolt_t=-55.0,          # cradle bolts, offset along body "up" from the body centre
    seam_pitch=80.0,       # max screw spacing along any seam
    seam_end=20.0,         # first/last screw from a seam end (clears corner flanges and iron)
)

PRINTER = dict(
    name="Elegoo Centauri Carbon 2",
    bed=(256.0, 256.0, 256.0),
    max_part=250.0,        # split anything larger
    nozzle=0.4, layer=0.2,
    filament="PETG (matte black) or PLA Matte black",
)

# Heat-set inserts: one parameter set per thread, used by every hole.
INSERTS = {
    "M3": dict(od=4.8, length=5.7, hole_d=4.0),            # common M3 x 5.7 inserts (OD 4.6-5.0)
    "M4": dict(od=6.0, length=8.1, hole_d=5.6),            # placeholder, for the foot screws
}

FASTENERS = dict(
    insert_extra=1.0,      # hole depth = insert length + this
    insert_lead_in=0.2,    # 45 deg chamfer at the insert hole mouth
    insert_floor=1.5,      # material behind the hole bottom
    boss_wall=2.0,         # boss OD >= insert OD + 2 x this (rounded up to 0.5 mm)
    iron_d=12.0, iron_len=25.0,  # soldering-iron access cylinder, free along the insert axis
    engage_min=4.0,        # screw thread engagement in the insert
    m3_clear=3.4,
    m3_head_d=5.5, m3_head_h=3.0,
    cbore_d=6.5,           # counterbore, only where a head would stick out of an outer face
    screw_lengths=(8, 12, 16),
    quarter_clear=6.8,     # 1/4"-20 clearance slot width
    dowel_d=4.0, dowel_h=4.0, dowel_fit=0.25,
)

ROUNDING = dict(
    edge_r=1.5,            # outer edges
    corner_r=3.0,          # large outer corners (panel/base plan corners, front opening edges)
    bed_chamfer=0.8,       # 45 deg chamfer on edges touching the print bed
    fillet_in_r=2.0,       # inside corners: ribs, bosses, flanges, channel walls on their skin or plate
    fillet_in_big=3.0,     # inside corners of the cheeks (gussets and feet)
    fillet_solids=True,    # inside fillets as solids (csg_fillet.py); False builds without them
    brep_round=True,       # try SolidCraft B-rep fillets first (brep_round.py), mesh pipeline as fallback
    brep_budget_s=240,     # time budget of the B-rep rounding of one part (edges left then stay sharp)
    lead_in_r=0.3,         # tongues, dowels, keys, groove and hole mouths
    fallback_r=(0.8, 0.4),  # tried in turn where a radius does not fit the faces beside an edge
    sharp_deg=30.0,        # an edge is sharp when its faces turn by more than this (interior < 150 deg)
)

# Feet: printed stubs that replicate the Centauri Carbon 2 stock foot, so the genuine Elegoo
# "Anti-Vibration Feet for Centauri Carbon 2 Series" silicone sleeves slip on as on the printer.
# M = community CAD of the CC1/CC2 stock foot (medium confidence): measure on your own CC2.
FEET = dict(
    foot_d_top=31.5,       # M  stub diameter at the base end
    foot_d_bottom=26.5,    # M  stub diameter at the table end (about 4.9 deg taper)
    foot_h=29.0,           # M  stub height
    foot_screw="M3",       # thread of the stub screw and of the insert in the base
    foot_engage=4.5,       # screw engagement in the base insert
    foot_recess_clear=0.3,  # locating recess diameter = stub top diameter + this
    foot_recess_depth=1.5,  # locating recess in the base underside
    sleeve_d=40.0,         # L  assumed max sleeve outside diameter
    sleeve_clear=5.0,      # sleeve to base edges, seam and other features
)

# Controlled LED lighting: mechanical interface from the lighting/electronics design
# (electronics/DESIGN.md). World coordinates as in geom.py.
LIGHTING = dict(
    ch_w=16.0,             # LED channel inner width; 8 mm FPC strip stuck centred on the skin
    ch_wall=1.6,           # channel wall thickness (outer width 19.2)
    ch_h=12.6,             # wall height above the skin: groove 10.0 + 1.4 + lip 1.2
    groove_z=10.0,         # cover groove lower edge above the skin (strip top to cover = 8 mm)
    groove_h=1.4, groove_d=1.0,                # cover groove in each wall
    cover_w=17.7, cover_t=1.2,                 # natural PETG cover, length = channel length - 1
    end_wall=1.6,          # closed channel end
    wire_hole_d=3.0,       # strip-lead hole in the end wall (closed, so its edges round all round)
    wire_hole_lift=1.5,    # hole bottom above the skin, clear of its mouth rounds (the requested notch at
                           # skin level, as a closed hole)
    visor=8.0,             # wall runs: the +Y wall (scanner side) runs this far past the cover face
    roof_run_x=90.0, roof_run_y=(-95.0, 65.0),  # roof_front underside, channel Y range, at X = +-90
    wall_run_y=95.0, wall_run_z=(170.0, 305.0),  # upper rear side panels, channel Z range, at Y 95
    harness_hole_d=4.0,    # harness hole through the roof lips and centre rib, wire_hole_lift off the skin
    riser_y=-50.0,         # strip harness up the inside of the -X front wall at this Y
    roof_cross_y=58.0,     # harness across the roof_front underside (clips), to both roof channel ends
    lip_hole_y=82.0,       # harness over the Y 72 seam: hole in the roof_rear side lips, to the wall runs
    sensor_tip=(-110.0, -40.0, 180.0),         # TEPT5700 dome tip, on side_left_front_upper
    sensor_tilt=10.0,      # axis tilted from vertical towards -Y (the open front)
    sensor_h=8.6, sensor_bore=5.2, sensor_cb_d=6.0, sensor_cb_h=1.5,
    sensor_collar_d=16.0, sensor_collar_below=0.5,  # flat collar under the tip: hides platter and model
    board_w=60.0, board_h=40.0, board_t=1.6,   # perfboard
    board_hole_dx=53.34, board_hole_dy=33.02,  # M3 hole centres
    board_free=22.0,       # free height above the board (components)
    bay_y=195.0,           # board centre on base_rear
    standoff_h=6.0,        # board standoffs (>= 5)
    bay_wall=2.0, bay_top=2.5,
    bay_cable_d=10.0,      # harness hole in the bay cover wall facing the back wall, 3.5 mm above the base
    panel_holes=(("DC barrel jack DC-022B", 8.2), ("toggle MTS-102", 6.5), ("potentiometer 16 mm", 7.5),
                 ("power LED 3 mm", 3.1)),    # back_lower, D mm, left to right seen from behind
    pot_tab_d=3.2, pot_tab_off=8.0,            # pot anti-rotation tab hole, above the pot centre
    panel_z=35.0, panel_pitch=25.0,
    cable_post_w=3.0, cable_slot=4.0, cable_post_h=6.0,   # cable guide: two posts with a slot
)

DEFAULT_SCANNER = "mini2"
DEFAULT_TURNTABLE = "revopoint_a230_ii"


def load(scanner=DEFAULT_SCANNER, turntable=DEFAULT_TURNTABLE, **overrides):
    """Flat namespace of every parameter; overrides win (e.g. load(distance=200))."""
    p = {}
    for group in (SCANNERS[scanner], TURNTABLES[turntable], POSE, ENCLOSURE, PRINTER, FASTENERS,
                  ROUNDING, FEET, LIGHTING):
        for k, v in group.items():
            if k in p and k != "label":
                raise KeyError(f"duplicate parameter {k}")
            p[k] = v
    p["scanner_label"] = SCANNERS[scanner]["label"]
    p["turntable_label"] = TURNTABLES[turntable]["label"]
    p["scanner"], p["turntable"] = scanner, turntable
    for k, v in overrides.items():
        if k not in p:
            raise KeyError(f"unknown parameter {k}")
        p[k] = v
    p["inserts"] = {t: insert_spec(p, t) for t in INSERTS}
    return SimpleNamespace(**p)


def insert_spec(p, thread):
    """Hole and boss sizes of one heat-set insert, from the shared rules."""
    s = dict(INSERTS[thread])
    s["hole_depth"] = s["length"] + p["insert_extra"]
    s["boss_d"] = math.ceil((s["od"] + 2 * p["boss_wall"]) * 2) / 2
    s["boss_len"] = s["hole_depth"] + p["insert_floor"]        # boss depth along the axis
    s["thread"] = thread
    return s
