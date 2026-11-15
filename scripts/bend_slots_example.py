#!/usr/bin/env python3
"""Generate the bend-slot specimen with rounded or rectangular cut ends.

SPDX-License-Identifier: MIT OR Apache-2.0
The profile is a creation option; resulting native dimensions remain editable.
"""

import argparse
import copy
import json
from pathlib import Path


PROFILES = ("rounded", "rectangular")


def build_example(profile="rounded"):
    if profile not in PROFILES:
        raise ValueError("profile must be rounded or rectangular")
    root = Path(__file__).resolve().parents[1]
    recipe = json.loads((root / "examples/sheet-bend-slots-prototype.json").read_text())
    if profile == "rounded":
        return recipe
    commands = []
    for source in recipe["commands"]:
        command = copy.deepcopy(source)
        name, params = command["command"], command["params"]
        if name == "parameters.add" and params["name"] == "slot_count":
            params["expression"] = "floor((specimen_width-2*corner_r-2*slot_margin+slot_bridge)/slot_pitch)"
        elif name == "sketch.draw.dimensioned" and params["command"] == "sketch.slot.overall":
            command = {"command": "sketch.rectangle.two_point", "params": {
                "p0": ["slot_start", "bend_y-slot_width/2"],
                "p1": ["slot_start+slot_length", "bend_y+slot_width/2"],
            }}
        elif name == "parameters.change" and set(params.get("changes", {})) == {"d6", "d7", "d8"}:
            continue
        elif name == "sketch.pattern.rectangular":
            params["entities"] = ["l1", "l2", "l3", "l4"]
        elif name == "sketch.point" and params.get("id", "").endswith("ct"):
            continue
        elif name == "sketch.arc.center_point" and params.get("center", "").endswith("ct"):
            command = {"command": "sketch.line", "params": {
                "points": [params["start"], params["end"]],
            }}
        commands.append(command)
    return {"commands": commands}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="rounded")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(json.dumps(build_example(args.profile), indent=2) + "\n")
    print(str(args.out))


if __name__ == "__main__":
    main()
