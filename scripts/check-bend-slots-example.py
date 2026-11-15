#!/usr/bin/env python3
"""Check the generic bend-slot command example with an installed SolidCraft CLI.

SPDX-License-Identifier: MIT OR Apache-2.0
This is a model verification script, not a SolidCraft application implementation.
"""

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile


BODY = "Hand-bend specimen"
DEFAULTS = {
    "specimen_width": 60.0, "specimen_depth": 100.0,
    "specimen_flange": 20.0, "specimen_t": 2.0,
    "specimen_r": 2.0, "specimen_angle": 45.0,
    "specimen_k": 0.5, "slot_length": 7.0,
    "slot_width": 1.0, "slot_bridge": 3.0,
    "slot_margin": 2.0, "corner_r": 3.0,
}
CASES = {
    "reopen": {},
    "width-80": {"specimen_width": "80 mm"},
    "angle-90": {"specimen_angle": "90 deg"},
    "angle-30": {"specimen_angle": "30 deg"},
    "thin": {"specimen_t": "1.5 mm", "specimen_r": "1.5 mm"},
    "slot-size": {"slot_length": "8 mm", "slot_width": "1.2 mm",
                  "slot_bridge": "4 mm", "slot_margin": "3 mm"},
    "corner-5": {"corner_r": "5 mm"},
    "depth-120": {"specimen_depth": "120 mm"},
    "wide-slots": {"slot_width": "3 mm"},
}


def run(cli, script, output, design=None, save=None):
    args = [cli, "run", str(script), "--results", "--param-check", "strict",
            "--json-out", str(output)]
    if design:
        args += ["--in", str(design)]
    if save:
        args += ["--save", str(save)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return json.loads(output.read_text())


def write_script(path, commands):
    path.write_text(json.dumps({"commands": commands}, indent=2) + "\n")
    return path


def inspect_commands():
    return [
        {"command": "sheet.flat_pattern", "params": {"body": BODY}},
        {"command": "inspect.measure", "params": {"bodies": [BODY]}},
    ]


def expected(changes):
    p = DEFAULTS | {k: float(v.split()[0]) for k, v in changes.items()}
    width, depth = p["specimen_width"], p["specimen_depth"]
    thickness, radius = p["specimen_t"], p["specimen_r"]
    angle = math.radians(p["specimen_angle"])
    length, slot_width = p["slot_length"], p["slot_width"]
    bridge, corner = p["slot_bridge"], p["corner_r"]
    count = math.floor((width - 2*corner - 2*p["slot_margin"] + bridge) / (length + bridge))
    allowance = angle * (radius + p["specimen_k"]*thickness)
    setback = (radius + thickness) * math.tan(angle/2)
    flat_length = depth + 2*p["specimen_flange"] - 4*setback + 2*allowance
    slot_area = (length - slot_width)*slot_width + math.pi*slot_width**2/4
    # Four outer corners. Each bend-end relief removes a slot-height throat
    # and the scraps outside two quarter circles in the adjacent panels.
    outer_scraps = 4*corner**2*(1 - math.pi/4)
    end_reliefs = 4*(corner*slot_width + 2*corner**2*(1 - math.pi/4))
    volume = (width*flat_length - 2*count*slot_area - outer_scraps - end_reliefs)*thickness
    return p, 2*count, flat_length, volume


def dxf_entities(dxf):
    lines = dxf.splitlines()
    pairs = [(int(lines[i].strip()), lines[i+1].strip()) for i in range(0, len(lines)-1, 2)]
    section, current, entities = None, None, []
    for i, (code, value) in enumerate(pairs):
        if code == 2 and i and pairs[i-1] == (0, "SECTION"):
            section = value
        if section != "ENTITIES":
            continue
        if code == 0:
            if current:
                entities.append(current)
            current = {"type": value}
        elif current is not None and code == 8:
            current["layer"] = value
        elif current is not None and code in (10, 20, 11, 21):
            current[str(code)] = float(value)
    return entities


def dxf_counts(dxf):
    return collections.Counter((e.get("layer"), e["type"]) for e in dxf_entities(dxf))


def check_relief_alignment(flat, entities, p):
    angle = math.radians(p["specimen_angle"])
    allowance = angle*(p["specimen_r"] + p["specimen_k"]*p["specimen_t"])
    centre = (p["specimen_r"] + p["specimen_t"])*math.tan(angle/2) - allowance/2
    centres = [centre, p["specimen_depth"] - centre]
    width = p["slot_width"]
    errors = []
    for y in centres:
        for x in [p["corner_r"], p["specimen_width"] - p["corner_r"]]:
            matches = []
            for e in entities:
                if e.get("layer") != "OUTLINE" or e["type"] != "LINE":
                    continue
                low, high = sorted([e["20"], e["21"]])
                error = max(abs(e["10"] - x), abs(e["11"] - x),
                            abs(low - (y-width/2)), abs(high - (y+width/2)))
                if error < 1e-6:
                    matches.append(error)
            assert len(matches) == 1, ("relief throat must align with slot", x, y, matches)
            errors.extend(matches)
    for shape in flat["cutout_shapes"]:
        arcs = [s["arc"] for s in shape["segments"] if "arc" in s]
        low = min(a["center"][1]-a["radius"] for a in arcs)
        high = max(a["center"][1]+a["radius"] for a in arcs)
        y = min(centres, key=lambda v: abs((low+high)/2-v))
        errors += [abs(low-(y-width/2)), abs(high-(y+width/2))]
    assert max(errors) < 1e-6, errors
    return max(errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", default="solidcraft-cli")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    work = args.output_dir or Path(tempfile.mkdtemp(prefix="solidcraft-bend-slots-"))
    work.mkdir(parents=True, exist_ok=True)
    fixture = Path(__file__).resolve().parents[1] / "examples/sheet-bend-slots-prototype.json"
    base = work / "prototype.sc"
    run(args.cli, fixture, work / "build.json", save=base)
    receipts = []
    for name, changes in CASES.items():
        commands = []
        if changes:
            commands.append({"command": "parameters.change", "params": {"changes": changes}})
        commands += inspect_commands() + [
            {"command": "sketch.inspect", "params": {"sketch": "Bend slot seed"}},
            {"command": "sketch.inspect", "params": {"sketch": "Rounded bend ends"}},
        ]
        script = write_script(work / (name + ".json"), commands)
        saved = work / (name + ".sc")
        results = run(args.cli, script, work / (name + "-results.json"), base, saved)
        flat, measured, seed, ends = results[-4:]
        body = measured["bodies"][0]
        p, slots, flat_length, volume = expected(changes)
        assert len(flat["cutouts"]) == slots, name
        assert body["closed"] and body["sheet_metal"], name
        assert abs(flat["flat_size_mm"][0] - p["specimen_width"]) < 1e-6, name
        assert abs(flat["flat_size_mm"][1] - flat_length) < 1e-6, name
        assert abs(body["volume_mm3"] - volume) < 1e-3, name
        assert seed["dof"] == 0 and ends["dof"] == 0, name
        for shape in flat["cutout_shapes"]:
            arcs = [s["arc"] for s in shape["segments"] if "arc" in s]
            assert len(arcs) == 2, name
            assert all(abs(a["radius"] - p["slot_width"]/2) < 1e-6 for a in arcs), name
        query = write_script(work / "inspect-saved.json", inspect_commands() + [
            {"command": "sheet.export_dxf", "params": {"body": BODY, "bend_lines": False}},
        ])
        reopened = run(args.cli, query, work / (name + "-reopened.json"), saved)
        assert len(reopened[0]["cutouts"]) == slots, name
        assert reopened[1]["bodies"][0]["closed"], name
        assert abs(reopened[1]["bodies"][0]["volume_mm3"] - body["volume_mm3"]) < 1e-6, name
        alignment_error = check_relief_alignment(reopened[0], dxf_entities(reopened[2]["dxf"]), p)
        receipt = {"case": name, "changes": changes, "slots": slots,
                   "closed": True, "sheet_metal": True, "sketch_dof": [0, 0],
                   "saved_variant_reopened": True, "flat_size_mm": flat["flat_size_mm"],
                   "expected_volume_mm3": volume, "measured_volume_mm3": body["volume_mm3"],
                   "volume_error_mm3": body["volume_mm3"] - volume,
                   "relief_height_mm": p["slot_width"], "aligned_reliefs": 4,
                   "max_alignment_error_mm": alignment_error}
        receipts.append(receipt)
        print(name + ": pass", flush=True)
    query = write_script(work / "dxf.json", [
        {"command": "sheet.export_dxf", "params": {"body": BODY, "bend_lines": False}},
    ])
    counts = dxf_counts(run(args.cli, query, work / "dxf-results.json", base)[0]["dxf"])
    assert counts[("CUT", "ARC")] == 20 and counts[("CUT", "LINE")] == 20
    assert counts[("OUTLINE", "ARC")] == 12
    assert not any(layer in ("BEND_UP", "BEND_DOWN") for layer, _ in counts)
    invalid = work / "invalid-must-not-save.sc"
    if invalid.exists():
        raise RuntimeError("Use an output folder without an invalid-must-not-save.sc file")
    query = write_script(work / "invalid.json", [
        {"command": "parameters.change", "params": {"name": "specimen_width", "expression": "10 mm"}},
    ])
    before = hashlib.sha256(base.read_bytes()).hexdigest()
    result = subprocess.run([args.cli, "run", str(query), "--in", str(base), "--save", str(invalid)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode != 0 and not invalid.exists()
    assert hashlib.sha256(base.read_bytes()).hexdigest() == before
    report = {"status": "passed", "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
              "tests": receipts, "dxf": {"cut_arcs": 20, "cut_lines": 20, "outline_arcs": 12,
                                         "bend_markings_omitted": True},
              "invalid_count": {"refused": True, "source_unchanged": True,
                                "error": result.stderr.strip()[-1500:]}}
    (work / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print("DXF contours, invalid-count refusal and save/reopen: pass")
    print("Results: " + str(work / "verification.json"))


if __name__ == "__main__":
    main()
