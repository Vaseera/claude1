"""
Xalatath - flesh physics (Kiriko's KP_Flesh_Physics, transferred)
=================================================================

Adds the same Geometry Nodes flesh simulation used on Kiriko to
'Xalatath - HD Body', with Kiriko's painted physics maps transferred onto
Xalatath's body by matching joints.

How to use
----------
1. Put xal_kp_weights.json next to your Xalatath .blend file (or set
   WEIGHTS_FILE below).
2. Set KIRI_BLEND to the path of KiriContent_005.blend. The physics node
   setup is appended from it.
3. Open this file in Blender's Text Editor and press Run Script.
4. A "Xalatath Physics" tab appears in the 3D view sidebar (N panel).
   Turn Flesh Physics ON, then play the timeline from the first frame.

Safe to run more than once: it rebuilds the modifier and maps each time.

Notes
-----
- The simulation runs forward from the scene start frame. After changing
  settings, jump back to the start frame and play again.
- Objects in the 'KP_Colliders' collection push the flesh (hands, props).
  Xalatath's own hands are colliders already ('Own Hands Collide').
- Settings in metres (gaps, contact depth) are scaled to Xalatath's size.
"""

import os
import json
import bpy

KIRI_BLEND = ""                  # full path to KiriContent_005.blend
WEIGHTS_FILE = ""                # empty = xal_kp_weights.json next to the .blend
BODY_NAME = "Xalatath - HD Body"
RIG_NAME = "RIG-Xalatath"
NODE_GROUP = "KP_Flesh_Physics"
MOD_NAME = "KP_Flesh_Physics"
COLLIDERS = "KP_Colliders"
TOGGLE_PROP = "Flesh_Physics"

# Xalatath is about 1.25x Kiriko's size; these inputs are distances
SCALE = 1.25
SETTINGS = {
    "Stiffness": 350.0,
    "Firm Areas Multiplier": 6.0,
    "Damping": 7.0,
    "Spread": 60000.0,
    "Extra Damping": 12.0,
    "Own Hands Collide": True,
    "Collision Gap": 0.001 * SCALE,
    "Friction": 0.45,
    "Max Face Drag": 0.004 * SCALE,
    "Wrap Distance": 0.02 * SCALE,
    "Normal Smoothing": 10,
    "Contact Depth": 0.09 * SCALE,
    "Substeps": 20,
    "Amount": 1.0,
    "Bulge": 0.6,
    "Bulge Width": 12,
    "Inertia": 0.0,
    "Hips & Thighs": True,
    "Stomach & Torso": True,
    "Breasts": True,
    "Calves & Knees": True,
    "Face (Lips & Cheeks)": False,
}

ZONES = ("Hips & Thighs", "Stomach & Torso", "Breasts", "Calves & Knees", "Face (Lips & Cheeks)")

PANEL_SOURCE = '''import bpy
ZONES = %r
class XAL_PT_flesh_physics(bpy.types.Panel):
    bl_label = "Xalatath Physics"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Xalatath Physics"
    def draw(self, context):
        lay = self.layout
        r = bpy.data.objects.get(%r)
        body = bpy.data.objects.get(%r)
        if r is None or %r not in r or body is None:
            lay.label(text="Xalatath rig / body not found"); return
        on = bool(r[%r])
        row = lay.row(); row.scale_y = 1.6
        row.prop(r, '["%s"]', text=("Flesh Physics: ON" if on else "Flesh Physics: OFF (fast)"), toggle=True,
                 icon=('PHYSICS' if on else 'HIDE_ON'))
        gm = body.modifiers.get(%r)
        if gm is None or gm.node_group is None: return
        ids = {it.name: it.identifier for it in gm.node_group.interface.items_tree if getattr(it, 'in_out', '') == 'INPUT'}
        box = lay.box(); box.enabled = on
        box.label(text="Areas (off areas cost no CPU):")
        col = box.column(align=True)
        for name in ZONES:
            if name in ids:
                col.prop(gm, '["%%s"]' %% ids[name], text=name, toggle=True)
        box2 = lay.box(); box2.enabled = on
        box2.label(text="Feel:")
        for name in ("Amount", "Stiffness", "Damping", "Substeps"):
            if name in ids:
                box2.prop(gm, '["%%s"]' %% ids[name], text=name)
        lay.label(text="Play from the first frame to simulate.")
def register():
    try: bpy.utils.unregister_class(bpy.types.XAL_PT_flesh_physics)
    except Exception: pass
    bpy.utils.register_class(XAL_PT_flesh_physics)
register()
''' % (ZONES, RIG_NAME, BODY_NAME, TOGGLE_PROP, TOGGLE_PROP, TOGGLE_PROP, MOD_NAME)


def blend_dir():
    return bpy.path.abspath("//")


def append_node_group():
    if NODE_GROUP in bpy.data.node_groups:
        return bpy.data.node_groups[NODE_GROUP]
    path = bpy.path.abspath(KIRI_BLEND) if KIRI_BLEND else os.path.join(blend_dir(), "KiriContent_005.blend")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Set KIRI_BLEND to the path of KiriContent_005.blend (tried: {path})")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.node_groups = [NODE_GROUP]
    ng = bpy.data.node_groups[NODE_GROUP]
    # the default collider collection came from Kiriko's file; the modifier gets Xalatath's own
    for it in ng.interface.items_tree:
        if getattr(it, "socket_type", "") == "NodeSocketCollection":
            it.default_value = None
    return ng


def load_weights(body):
    path = bpy.path.abspath(WEIGHTS_FILE) if WEIGHTS_FILE else os.path.join(blend_dir(), "xal_kp_weights.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"xal_kp_weights.json not found: {path}")
    with open(path) as f:
        data = json.load(f)
    n = len(body.data.vertices)
    if data["_meta"]["verts"] != n:
        raise RuntimeError(f"{BODY_NAME} has {n} vertices but the weights were made for {data['_meta']['verts']}")
    for name, values in data.items():
        if name.startswith("_"):
            continue
        vg = body.vertex_groups.get(name) or body.vertex_groups.new(name=name)
        vg.remove(range(n))
        by_weight = {}
        for i, w in enumerate(values):
            if w > 0.0005:
                by_weight.setdefault(round(w, 3), []).append(i)
        for w, idx in by_weight.items():
            vg.add(idx, w, "REPLACE")


def colliders_collection():
    col = bpy.data.collections.get(COLLIDERS)
    if col is None:
        col = bpy.data.collections.new(COLLIDERS)
        bpy.context.scene.collection.children.link(col)
    return col


def add_modifier(body, ng, col):
    old = body.modifiers.get(MOD_NAME)
    if old:
        body.modifiers.remove(old)
    mod = body.modifiers.new(MOD_NAME, "NODES")
    mod.node_group = ng
    # run on the posed body, before subdivision
    arm_idx = max(i for i, m in enumerate(body.modifiers) if m.type == "ARMATURE")
    body.modifiers.move(body.modifiers.find(MOD_NAME), arm_idx + 1)
    ids = {it.name: it.identifier for it in ng.interface.items_tree
           if it.item_type == "SOCKET" and it.in_out == "INPUT"}
    mod[ids["Colliders"]] = col
    for name, value in SETTINGS.items():
        if name in ids:
            mod[ids[name]] = value
    return mod


def add_toggle(rig, body):
    if TOGGLE_PROP not in rig:
        rig[TOGGLE_PROP] = False
    ui = rig.id_properties_ui(TOGGLE_PROP)
    ui.update(description="Turn Xalatath's flesh simulation on/off (off = fast playback)")
    for path in (f'modifiers["{MOD_NAME}"].show_viewport', f'modifiers["{MOD_NAME}"].show_render'):
        body.driver_remove(path)
        fc = body.driver_add(path)
        d = fc.driver
        d.type = "SCRIPTED"
        v = d.variables.new()
        v.name = "on"
        v.targets[0].id = rig
        v.targets[0].data_path = f'["{TOGGLE_PROP}"]'
        d.expression = "on"
    txt = bpy.data.texts.get("xalatath_physics_toggle.py") or bpy.data.texts.new("xalatath_physics_toggle.py")
    txt.clear()
    txt.write(PANEL_SOURCE)
    txt.use_module = True        # registers on file load when scripts are allowed
    exec(compile(PANEL_SOURCE, txt.name, "exec"), {"__name__": "__main__"})


def main():
    body = bpy.data.objects[BODY_NAME]
    rig = bpy.data.objects[RIG_NAME]
    ng = append_node_group()
    load_weights(body)
    col = colliders_collection()
    add_modifier(body, ng, col)
    add_toggle(rig, body)
    print("Flesh physics added to", BODY_NAME)


main()
