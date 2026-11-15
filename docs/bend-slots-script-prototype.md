# Bend slots and rounded panel ends through existing commands

Status: script prototype, verified with installed SolidCraft 0.42.0 on 15 November 2026.
No SolidCraft application or kernel source is changed. No new command is registered.

## Result

Existing commands can cut rounded slots across bends and round the panel corners beside
their ends. Unfold/refold, parameter edits, native save/reopen and exact DXF cut contours
work on the generic specimen in `examples/sheet-bend-slots-prototype.json`.

The example is a new design, not a script to run directly on an existing enclosure.
It makes one sheet with two opposing 45-degree flanges. Each bend gets five slots.
The rounded default uses semicircular closed ends on both the slots and relief
throats. Four open reliefs round the adjacent panel corners at the bend ends. The four free
outer corners are rounded too. The result remains one closed sheet-metal solid.

The experiment supports a script/command-plugin first implementation. It does not
establish a need for a custom SolidCraft application build.

## Run and verify

```sh
solidcraft-cli run examples/sheet-bend-slots-prototype.json --param-check strict --save /tmp/bend-slots.sc
python3 scripts/bend_slots_example.py --profile rectangular --out /tmp/rectangular-bend-slots.json
solidcraft-cli run /tmp/rectangular-bend-slots.json --param-check strict --save /tmp/rectangular-bend-slots.sc
python3 scripts/check-bend-slots-example.py --cli solidcraft-cli --profile all
```

The checker writes native designs and a verification receipt to a temporary folder.
`--output-dir` selects another output folder. It exports DXF into a command response
for inspection; it creates no STEP files and changes no open desktop document.

## Profile option

`--profile rounded|rectangular` switches the slot ends and relief throat ends together.
Rounded is the default. Its end radius is `slot_width/2`; rectangular uses straight ends.
Both modes share the same slot height, relief height and bend centre lines. The larger
panel-corner and entry-flare radii remain controlled separately by `corner_r`.

This is a script creation option. Regenerate the example to change profile; there is
no new in-app dropdown or shape-switching timeline evaluator. Dimensions in either
generated design remain native parameters and update without running the script again.

For laser-cut, hand-bent parts, rounded ends are the proposed default: both shapes
are straightforward to cut, while sharp rectangular corners concentrate stress.
This follows [fabricator guidance](https://sendcutsend.com/blog/guide-to-designing-bend-reliefs/);
it is not a quote or a claim of a measured price difference.

## Existing operations used

1. Add the sheet and layout parameters before their consumers.
2. Make the base and flanges under a named sheet-metal rule.
3. Unfold the sheet.
4. Create one rounded slot with `sketch.draw.dimensioned` and `sketch.slot.overall`.
5. Change its generated location dimensions to expressions over the layout parameters.
6. Make an associative `sketch.pattern.rectangular`, with expression-driven quantities
   and spacings, then cut the profiles through the sheet in one extrusion.
7. Cut the material outside a rounded perimeter to round the four free corners.
8. Cut the rounded bend-end reliefs. Their lines and arcs use parameter-bound sketch
   points. Their centres follow the bend position, and their throat height follows
   `slot_width`, keeping the reliefs aligned with the slots. The closed throat end
   is a semicircle in rounded mode and a line in rectangular mode.
9. Refold and inspect the resulting sheet and its flat pattern.

There are no Move, Rotate or Scale features. The ordinary native feature history,
not an external callback, owns subsequent parameter recomputation.

The slot creator does not accept expression coordinates for `p0` and `p1` in the
tested build. The dimensioned wrapper provides driving length and width dimensions.
Its returned location dimension names are then rebound to expressions. The example
records the deterministic names from its fresh design. A reusable plugin must read
the actual returned names, never assume those names in an existing document.

## Parameters and layout

All values below are geometry test inputs, not manufacturing recommendations.

| Parameter | Specimen value | Meaning |
| --- | --- | --- |
| `specimen_width` | 60 mm | Bend length before end reliefs |
| `specimen_depth` | 100 mm | Base depth |
| `specimen_flange` | 20 mm | Outer-sharp flange height |
| `specimen_t` | 2 mm | Sheet thickness |
| `specimen_r` | 2 mm | Modelled inside bend radius |
| `specimen_angle` | 45 deg | Bend angle |
| `specimen_k` | 0.5 | Analytic test control, not a calibrated material K-factor |
| `slot_length` | 7 mm | Overall slot length, including rounded ends |
| `slot_width` | 1 mm | Slot and relief throat height across the bend; slot end radius is half this |
| `slot_bridge` | 3 mm | Clear material between consecutive slots |
| `slot_margin` | 2 mm | Minimum clearance from a relieved bend end |
| `corner_r` | 3 mm | Free-corner radius and bend-end setback/round radius |

The pitch is `slot_length + slot_bridge`. The nominal repeat cut fraction is
`slot_length / pitch`; it is 70% here. End margins and the integer slot count make
the cut fraction over a complete bend different from this nominal repeat fraction.
Neither number is a strength or hand-bending qualification.

Let `cap_radius` be `slot_width/2` for rounded ends, or zero for rectangular ends.
The slot count is
`floor((specimen_width - 2*(corner_r+cap_radius) - 2*slot_margin + slot_bridge) / slot_pitch)`.
The occupied row is centred. An insufficient width gives an invalid count and the
native pattern command refuses the rebuild. No count is clamped to a misleading result.

Bend allowance is `angle_in_radians * (inside_radius + K * thickness)`.
The seed row, its second-row spacing and the bend-end cuts follow this expression.
Changing the bend angle therefore changes the cut positions as well as the bend itself.

The height of every end relief runs from `bend_centre - slot_width/2` to
`bend_centre + slot_width/2`, exactly matching the slot height and centre line.
The closed end is a semicircle of radius `slot_width/2` in rounded mode; its cap
centre lies at the previous straight end, so it reaches inward by that radius.
The slot-count expression reserves this extra space before measuring the minimum
end bridge. Rectangular mode retains the straight end and does not reserve a cap.
The rounded entry corners widen the outer mouth; `corner_r` controls that flare.

`corner_r` is deliberately coupled to the end setback in this first specimen.
A reusable tool should expose independent end setback, panel corner radius, seam gap,
minimum bridge and relief shape controls, subject to geometry validation.

## Checks performed

The checker runs ten cases for each profile (twenty cases with `--profile all`):
native reopen, width 80 mm, bends at 90 and 30 degrees, thickness/radius 1.5 mm,
changed slot dimensions, corner radius 5 mm, depth 120 mm, slot width 3 mm, and
width 57 mm (where a rounded cap needs one fewer slot to retain the end margin).
Each case is saved and opened again.

It checks:

- One closed sheet-metal body, with the expected number of physical cutouts.
- Zero degrees of freedom in the slot seed and bend-end relief sketches.
- Flat dimensions against the bend-allowance formula.
- Rounded slot and relief caps at half the specified width, or rectangular ends.
- Minimum end bridges measured from the relief tips, including the cap radius.
- All four relief throat heights and centre lines against the slot bounds, using
  exact DXF outline arcs or lines after reopening each saved variant.
  Rounded caps must cover the inward semicircle without gaps or overlaps.
- Volume against independent areas for the blank, capsule slots, quarter-circle
  corner scraps and bend-end reliefs (including their semicircular caps when selected).
  The absolute numerical comparison is 0.001 mm3.
- Saved variants reproduce their cut count and measured volume.
- Default rounded DXF: 20 slot arcs and 20 slot lines on `CUT`, and 16 arcs on `OUTLINE`.
  Rectangular DXF: 40 slot lines and no slot arcs on `CUT`, and 12 entry/corner arcs
  on `OUTLINE`.
  Bend marking layers are omitted in this check. The cuts therefore do not depend on
  a viewer interpreting a dashed bend-line style as cut geometry.
- A zero-slot count is refused without writing an output design or changing the source.

These checks verify CAD behaviour. They do not predict springback, material strength,
manual forming force, finished fit or fabrication tolerances. A material/laser/bend
coupon remains necessary before choosing production slot and bridge dimensions.

## Next implementation step

Build a command script or an explicitly run command plugin that accepts existing
selected bends and creates the same native features. Inspect the existing history
first, reuse its thickness/radius/angle parameters and sketch datums, and group only
the necessary new manufacturing cuts. Validate on a copy of a converted sheet before
changing a user's assembly.

The important remaining work is generic bend selection and coordinate/dependency
mapping. This specimen uses a known flat frame and explicit existing dimensions.
It does not yet handle arbitrary converted bends, closed seams, intersecting folds,
multiple sheet bodies, rotated components or automatic exclusion around other holes.
Clashing or under-sized cuts must be refused with a useful reason.

A command plugin is one-shot orchestration. The native features it creates retain
their normal parameter dependencies and rebuild without the plugin. A custom plugin
timeline evaluator is not required for the demonstrated dependencies. Return to a
core feature only if an actual selection, geometry or regeneration requirement
cannot be expressed with existing history.

## Source orientation and build boundary

The initial source inspection was pinned to
`d8ce0444d360e56032a3c060963d2099279dc810`.

- `crates/engine/src/cmd/sheet.rs`: existing sheet commands and flat/DXF responses.
- `crates/doc/src/sheet.rs`: sheet model, flat cuts, bend zones and corner reliefs.
- `crates/doc/src/document.rs`: retained native feature definitions.
- `crates/engine/src/schema/sheet.rs`: typed command contracts.
- `crates/ui-egui/src/dialogs_sheet.rs`: existing sheet dialogs.

`sheet.perforate` is not the bend-slot operation: its hole field stays clear of bend
zones and does not cut the B-rep. A general solid fillet can mark a sheet as altered
without updating its flat model. The prototype instead uses native sheet-aware cuts.

Related open work checked: #9245 (sheet representation), #16938 (app-side geometry),
#15357 (segment junction relief), #12651 (corner relief options), #15884 (slot expressions),
and #16284 (fold/hole sewing). None is claimed or changed by this prototype.

The runtime checks above use the installed application CLI, not a locally built fork.
An attempted `cargo xtask ci` stopped before compilation because the host's Cargo
registry cache directory conflicted with an existing path. No Rust application or
kernel changes are included, and no full source-build CI pass is claimed.
