# The rabbits by the witches' sign, warning you of them: sitting up, as in
# their picture, their ears up, shaking their heads at you.
#
# Made from Quaternius's Bunny (Ultimate Monsters, CC0, art/models/): a
# cartoon monster, grey and purple, with long arms. Here it's made a wild
# rabbit: brown, its belly cream and its ears pink inside, its arms short,
# and the size of one. Its colours come from its texture, a colour for each
# corner of each face (as the kits' props are). Its own clips (ANIMS) are
# kept, named as they are there.
#
# It stands on the ground at z = 0, facing -y.

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / "models/ultimate-monsters/Blends/Bunny.blend"))

ANIMS = ["Idle", "No", "Yes", "Duck", "Jump"]
TALL = 0.7  # metres, from its feet to its ears' tips (big for a rabbit: so it shows over the grass)
ARMS = 0.45  # its arms (and paws), as long as they were
SHOULDER = 0.37  # out from its middle, where its arms begin
# Its colours, for each of the Bunny's: its fur, round its eyes (dark: a rabbit's big eyes), its belly
# (and inside its ears, and its nose), and its eyes and mouth.
FUR, AROUND_EYES, BELLY, INNER_EAR, NOSE, DARK = (
    c.linear(h) for h in ("#8c6845", "#2a1f18", "#e3d3b8", "#d6a596", "#6b4536", "#1c1612")
)

skeleton = bpy.data.objects["CharacterArmature"]
body = bpy.data.objects["Bunny"]
bpy.data.objects.remove(bpy.data.objects["Carrot"], do_unlink=True)
for m in list(body.modifiers):
    if m.type == "NODES":  # (an outline drawn round it, in Blender)
        body.modifiers.remove(m)
skeleton.name = "rabbit"
body.name = "rabbit-body"

# ---- Its colours: from its texture, turned a wild rabbit's ------------------

image = next(i for i in bpy.data.images if i.size[0])
w, h = image.size
pixels = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)
mesh = body.data
uvs = mesh.uv_layers.active.data
layer = mesh.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="CORNER")
for poly in mesh.polygons:
    for li in poly.loop_indices:
        u, v = uvs[li].uv
        r, g, b = pixels[min(h - 1, int(v * h)), min(w - 1, int(u * w)), :3]
        p = mesh.vertices[mesh.loops[li].vertex_index].co
        if max(r, g, b) < 0.25:
            colour = DARK
        elif b > g + 0.05 and r > g + 0.05:  # (purple)
            colour = INNER_EAR if p.z > 2.25 else NOSE if p.z > 1.95 and p.y < -0.3 else BELLY
        elif b > r + 0.03:  # (blue-grey)
            colour = AROUND_EYES
        else:
            colour = FUR
        layer.data[li].color = c.vary(colour, 0.08, p * 2)
mesh.color_attributes.active_color = layer
mesh.materials.clear()
mesh.materials.append(c.vertex_material())

# ---- Its arms, made short: its mesh and its bones ----------------------------


def shorter(p):
    """Where a point on its arm goes, the arm drawn in towards its shoulder."""
    if abs(p.x) <= SHOULDER or p.z < 1.4:
        return p
    side = math.copysign(1, p.x)
    # (Its arms and paws slimmer, too: in towards the line along its arm.)
    x = side * (SHOULDER + (abs(p.x) - SHOULDER) * ARMS)
    return Vector((x, 0.2 + (p.y - 0.2) * 0.8, 1.83 + (p.z - 1.83) * 0.8))


for v in mesh.vertices:
    v.co = shorter(v.co)
bpy.context.view_layer.objects.active = skeleton
bpy.ops.object.mode_set(mode="EDIT")
for bone in skeleton.data.edit_bones:
    if bone.name.startswith(("UpperArm", "LowerArm", "Pinky", "Middle", "Index", "Thumb")):
        bone.head, bone.tail = shorter(bone.head), shorter(bone.tail)
bpy.ops.object.mode_set(mode="OBJECT")

# ---- The size of a rabbit ---------------------------------------------------

top = max((body.matrix_world @ v.co).z for v in mesh.vertices)
skeleton.scale = (TALL / top,) * 3

# ---- Its clips ---------------------------------------------------------------

skeleton.animation_data_create()
for track in list(skeleton.animation_data.nla_tracks):
    skeleton.animation_data.nla_tracks.remove(track)
for name in ANIMS:
    action = bpy.data.actions[name]
    track = skeleton.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, int(action.frame_range[0]), action)
    if hasattr(strip, "action_slot") and action.slots:
        strip.action_slot = action.slots[0]
skeleton.animation_data.action = None

if out:
    for o in bpy.data.objects:
        o.select_set(o in (skeleton, body))
    c.export(out, use_selection=True, export_animation_mode="NLA_TRACKS")

if preview:
    for o in list(bpy.data.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.scene.render.image_settings.file_format = "PNG"  # (the Bunny's file saves JPEGs)
    c.pose(skeleton, "Idle", 5)
    c.preview(preview, (0.35, -1.0, 0.3), (0, 0, 0.2), (0.4, 0.8, -1), lens=40)
    c.pose(skeleton, "No", 20)
    c.preview(preview.replace(".png", "-no.png"), (0.6, -0.8, 0.3), (0, 0, 0.2), (0.4, 0.8, -1), lens=40)
