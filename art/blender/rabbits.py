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
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
bpy.ops.wm.open_mainfile(filepath=str(HERE.parent / "models/ultimate-monsters/Blends/Bunny.blend"))

ANIMS = ["Idle", "No", "Yes", "Duck", "Jump"]
TALL = 0.7  # metres, from its feet to its ears' tips (big for a rabbit: so it shows over the grass)
ARMS = 0.45  # its arms (and paws), as long as they were
SHOULDER = 0.37  # out from its middle, where its arms begin
# Its colours, for each of the Bunny's: its fur (round its eyes, too: its own
# eyes go over them), its belly (and inside its ears, and its nose), and its
# mouth.
FUR, BELLY, INNER_EAR, NOSE, DARK = (c.linear(h) for h in ("#8c6845", "#e3d3b8", "#d6a596", "#6b4536", "#1c1612"))

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
pupils = []  # (where its eyes are painted, for its own eyes over them)
for poly in mesh.polygons:
    for li in poly.loop_indices:
        u, v = uvs[li].uv
        r, g, b = pixels[min(h - 1, int(v * h)), min(w - 1, int(u * w)), :3]
        p = mesh.vertices[mesh.loops[li].vertex_index].co
        eye_side = abs(p.x) > 0.12 and p.z > 2.0  # (either side of its face, where its eyes are)
        if max(r, g, b) < 0.25:
            colour = FUR if eye_side else DARK
            if eye_side:
                pupils.append(p.copy())
        elif b > g + 0.05 and r > g + 0.05:  # (purple)
            colour = INNER_EAR if p.z > 2.25 else NOSE if p.z > 1.95 and p.y < -0.3 else BELLY
        elif b > r + 0.03:  # (blue-grey, round its eyes: fur, under its eyes)
            colour = FUR
        else:
            colour = FUR
        layer.data[li].color = c.vary(colour, 0.08, p * 2)
mesh.color_attributes.active_color = layer
mesh.materials.clear()
mesh.materials.append(c.vertex_material())

# ---- Its eyes: solid, dark and glossy, over where they're painted ---------
# (Painted, a colour for each corner, their edges come ragged.)

EYE = (0.105, 0.45, 0.65)  # each eye's size, how deep it is for that, and how much of that is sunk into its face
EYE_COLOUR = c.linear("#120d0a")
head = skeleton.data.bones["Head"].head_local + Vector((0, 0, 0.2))  # (the middle of its head, roughly)
faces = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get(), deform=False)
eyes = bpy.data.materials.new("rabbit-eyes")
eyes.diffuse_color = (*EYE_COLOUR[:3], 1)
if hasattr(eyes, "use_nodes") and not eyes.use_nodes:
    eyes.use_nodes = True
bsdf = next(n for n in eyes.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
bsdf.inputs["Base Color"].default_value = (*EYE_COLOUR[:3], 1)
bsdf.inputs["Roughness"].default_value = 0.2  # (a glint of light in them)
for side in (1, -1):
    painted = [p for p in pupils if p.x * side > 0]
    middle = sum(painted, Vector()) / len(painted)
    # (A little round towards the front of its face from where they're painted,
    # where its face curves away: else they'd stand out past its head.)
    out_from = ((middle - head).normalized() + Vector((0, -0.7, 0))).normalized()
    hit, normal, _, _ = faces.ray_cast(head + out_from * 3, -out_from)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=EYE[0])
    # (Squashed, facing out of its face, and sunk into it: only a low dome shows.)
    turn = normal.to_track_quat("Z", "Y").to_matrix().to_4x4()
    place = Matrix.Translation(hit - normal * EYE[0] * EYE[1] * EYE[2]) @ turn @ Matrix.Diagonal((1, 1, EYE[1], 1))
    bmesh.ops.transform(bm, matrix=place, verts=bm.verts)
    verts = [tuple(v.co) for v in bm.verts]
    tris = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    eye = c.skinned(f"rabbit-eye-{'l' if side > 0 else 'r'}", verts, tris, [EYE_COLOUR] * len(verts),
                    [{"Head": 1.0}] * len(verts), skeleton)
    eye.data.materials.clear()
    eye.data.materials.append(eyes)

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
        o.select_set(o == skeleton or o.parent == skeleton)
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
