"""Print-time and filament estimates with the OrcaSlicer CLI, fully isolated.

Creates a throw-away --datadir (mktemp -d), copies Orca's system bundles and
the Elegoo vendor profile tree into it, slices every stl/*.stl on the
Centauri Carbon 2 0.4 / 0.20mm Standard profile, writes build/slice.json and
3mf/plate-<part>.3mf, then deletes the datadir. Never reads or writes the
user's ~/.config/OrcaSlicer presets (only copies its read-only system bundles).

Usage: python3 src/slice_orca.py [--filament petg|pla_matte] [--no-3mf]
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile

from sc import BUILD, ROOT

ORCA = os.path.expanduser("~/Applications/OrcaSlicer.AppImage")
ORCA_SYSTEM = os.path.expanduser("~/.config/OrcaSlicer/system")          # *.opc bundles
VENDOR_SRC = os.path.expanduser("~/.config/ElegooSlicer/system")         # plain-JSON Elegoo tree
MACHINE = "machine/ECC2/Elegoo Centauri Carbon 2 0.4 nozzle.json"
PROCESS = "process/ECC2/0.20mm Standard @Elegoo CC2 0.4 nozzle.json"
FILAMENTS = {"petg": "filament/ECC2/Elegoo PETG @ECC2.json",
             "pla_matte": "filament/ECC2/Elegoo PLA Matte @ECC2.json"}
OVERRIDES = ["--curr-bed-type=Textured PEI Plate", "--wall-loops=4", "--sparse-infill-density=20%",
             "--enable-support=0"]


def setup(tmp):
    data = os.path.join(tmp, "data", "system")
    os.makedirs(data)
    for f in glob.glob(os.path.join(ORCA_SYSTEM, "*.opc")):
        shutil.copy(f, data)
    vend = os.path.join(tmp, "vendor")
    os.makedirs(vend)
    shutil.copytree(os.path.join(VENDOR_SRC, "Elegoo"), os.path.join(vend, "Elegoo"))
    shutil.copy(os.path.join(VENDOR_SRC, "Elegoo.json"), vend)
    return os.path.join(tmp, "data"), os.path.join(vend, "Elegoo")


def slice_part(stl, datadir, vend, filament, out, export_3mf):
    os.makedirs(out, exist_ok=True)
    cmd = [ORCA, "--datadir", datadir,
           "--load-settings", f"{os.path.join(vend, MACHINE)};{os.path.join(vend, PROCESS)}",
           "--load-filaments", os.path.join(vend, FILAMENTS[filament]),
           *OVERRIDES, "--arrange", "1", "--slice", "0", "--export-statistics", "--outputdir", out]
    if export_3mf:
        cmd += ["--export-3mf", os.path.basename(export_3mf)]      # relative to --outputdir
    cmd.append(stl)
    for attempt in range(3):          # the CLI sometimes segfaults while writing the 3MF: retry, then without it
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if os.path.exists(os.path.join(out, "result.json")):
            break
        if attempt == 1 and export_3mf:
            print(f"note: {os.path.basename(stl)}: Orca crashed exporting the 3MF; sliced without it", flush=True)
            cmd = [c for c in cmd if c not in ("--export-3mf", os.path.basename(export_3mf))]
            export_3mf = None
    if not os.path.exists(os.path.join(out, "result.json")):
        raise RuntimeError(f"{stl}: orca crashed rc={r.returncode}\n{r.stderr[-1500:]}")
    res = json.load(open(os.path.join(out, "result.json")))
    if r.returncode != 0 or res.get("return_code", 0) != 0:
        raise RuntimeError(f"{stl}: orca failed rc={r.returncode} {res.get('error_string')}\n{r.stderr[-1500:]}")
    if export_3mf:
        shutil.move(os.path.join(out, os.path.basename(export_3mf)), export_3mf)
    st = json.load(open(os.path.join(out, "plate_1.statistics.json")))["summary"]
    return dict(time_s=round(st["time"]), weight_g=round(st["weight"], 1), volume_mm3=round(st["volume"]),
                layers=st["layer_count"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filament", nargs="*", default=["petg", "pla_matte"])
    ap.add_argument("--no-3mf", action="store_true")
    a = ap.parse_args()
    if subprocess.run(["pgrep", "-f", "-i", "orca-slicer"], capture_output=True).returncode == 0:
        print("note: an OrcaSlicer process is running; this run uses its own --datadir and does not touch it")
    tmp = tempfile.mkdtemp(prefix="scanenc-orca-")
    results = {}
    try:
        datadir, vend = setup(tmp)
        os.makedirs(os.path.join(ROOT, "3mf"), exist_ok=True)
        for stl in sorted(glob.glob(os.path.join(ROOT, "stl", "*.stl"))):
            name = os.path.basename(stl)[:-4]
            results[name] = {}
            for fil in a.filament:
                tmf = None if a.no_3mf or fil != a.filament[0] else os.path.join(ROOT, "3mf", f"plate-{name}.3mf")
                results[name][fil] = slice_part(stl, datadir, vend, fil, os.path.join(tmp, "out", name, fil), tmf)
            print(name, results[name], flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tot = {f: dict(time_s=sum(r[f]["time_s"] for r in results.values()),
                   weight_g=round(sum(r[f]["weight_g"] for r in results.values()), 1)) for f in a.filament}
    with open(os.path.join(BUILD, "slice.json"), "w") as f:
        json.dump(dict(profile=dict(machine=os.path.basename(MACHINE), process=os.path.basename(PROCESS),
                                    overrides=OVERRIDES), parts=results, total=tot), f, indent=1)
    print("total", tot)
    print("scratch datadir removed:", not os.path.exists(tmp))


if __name__ == "__main__":
    main()
