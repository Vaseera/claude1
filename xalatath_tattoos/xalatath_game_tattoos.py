"""
Xalatath - original game arm tattoos
====================================

Replaces the flat purple arm tattoos on 'Xalatath - HD Body' with the original
glyph tattoos from the game model (igc_xalatath3), baked onto the HD body.

How to use
----------
1. Put Xalatath_GameTattoo_Shade.png and Xalatath_GameTattoo_Mask.png in the
   same folder as your .blend file (or set TATTOO_DIR below).
2. Open this file in Blender's Text Editor and press Run Script (Alt+P).
3. Check the arms, then save. Both images are packed into the .blend.

Safe to run more than once. To go back to the old tattoos, run it again with
USE_GAME_TATTOOS = False.

What it changes
---------------
- Adds a 'TattooUV' map to the HD body. The skin's DiffuseUV mirrors both arms
  onto the same texture area, but the game model gives each arm different
  glyphs, so each arm gets its own space in this map.
- In the skin material, turns off the old 'Xalatath body markings' layer and
  multiplies the game glyphs over the skin (nodes named 'GameTattoo ...').
"""

import os
import bpy

TATTOO_DIR = ""             # empty = the folder the .blend file is saved in
USE_GAME_TATTOOS = True
BODY_NAME = "Xalatath - HD Body"
SKIN_MATERIAL = "Xalatath - HD skin with Void Elf underwear option"
OLD_MARKINGS_NODE = "Xalatath body markings"
SHADE_FILE = "Xalatath_GameTattoo_Shade.png"
MASK_FILE = "Xalatath_GameTattoo_Mask.png"
PREFIX = "GameTattoo"


def build_tattoo_uv(body, src_uv="DiffuseUV", name="TattooUV"):
    """Copy the arm UV island from src_uv into its own map, one half per arm."""
    me = body.data
    uv = me.uv_layers[src_uv].data

    # UV islands: faces sharing an edge with identical UVs on both sides
    parent = list(range(len(me.polygons)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edge_faces = {}
    for p in me.polygons:
        vs, lis = p.vertices, list(p.loop_indices)
        for k in range(len(vs)):
            a, b = vs[k], vs[(k + 1) % len(vs)]
            ua = tuple(round(c, 5) for c in uv[lis[k]].uv)
            ub = tuple(round(c, 5) for c in uv[lis[(k + 1) % len(vs)]].uv)
            edge_faces.setdefault((min(a, b), max(a, b)), []).append((p.index, {a: ua, b: ub}))
    for lst in edge_faces.values():
        if len(lst) == 2 and lst[0][1] == lst[1][1]:
            r1, r2 = find(lst[0][0]), find(lst[1][0])
            if r1 != r2:
                parent[r1] = r2

    # arm islands reach well out along the T-pose arm axis (object Y)
    ys = {}
    for p in me.polygons:
        ys.setdefault(find(p.index), []).append(p.center.y)
    arm_roots = {r for r, lst in ys.items() if max(abs(y) for y in lst) > 0.30}
    umax = max(uv[li].uv[0] for p in me.polygons if find(p.index) in arm_roots for li in p.loop_indices)
    scale = 0.49 / umax

    if name in me.uv_layers:
        me.uv_layers.remove(me.uv_layers[name])
    active_render = [l.name for l in me.uv_layers if l.active_render]
    active = me.uv_layers.active.name if me.uv_layers.active else None
    t = me.uv_layers.new(name=name, do_init=False).data
    for p in me.polygons:
        if find(p.index) in arm_roots:
            off = 0.5 if p.center.y < 0 else 0.0     # right arm -> right half
            for li in p.loop_indices:
                u, v = uv[li].uv
                t[li].uv = (u * scale + off, v)
        else:
            for li in p.loop_indices:
                t[li].uv = (0.999, 0.001)            # empty corner of the tattoo maps
    # adding a UV map must not change which map the skin renders with
    for l in me.uv_layers:
        l.active_render = l.name in active_render
    if active:
        me.uv_layers.active = me.uv_layers[active]


def load_image(folder, filename):
    path = os.path.join(folder, filename)
    img = bpy.data.images.get(filename)
    if img is None:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Tattoo image not found: {path}")
        img = bpy.data.images.load(path)
    if img.packed_file is None:
        img.pack()
    img.colorspace_settings.name = "Non-Color"
    return img


def socket(node, name, kind, out=False):
    socks = node.outputs if out else node.inputs
    return next(s for s in socks if s.name == name and s.type == kind)


def main():
    body = bpy.data.objects[BODY_NAME]
    mat = bpy.data.materials[SKIN_MATERIAL]
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links

    # remove anything from a previous run
    for n in [n for n in nodes if n.name.startswith(PREFIX)]:
        nodes.remove(n)

    old = nodes[OLD_MARKINGS_NODE]
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    fac = old.inputs["Fac"] if "Fac" in old.inputs else old.inputs[0]
    base = bsdf.inputs["Base Color"]

    if not USE_GAME_TATTOOS:
        repair = nodes.get("Repair arm marking coverage")
        if repair and not fac.is_linked:
            links.new(repair.outputs["Color"], fac)
        links.new(old.outputs["Color"], base)
        print("Game tattoos removed; old markings restored.")
        return

    folder = bpy.path.abspath(TATTOO_DIR) if TATTOO_DIR else bpy.path.abspath("//")
    shade_img = load_image(folder, SHADE_FILE)
    mask_img = load_image(folder, MASK_FILE)

    build_tattoo_uv(body)

    # old flat-purple markings off
    for l in list(fac.links):
        links.remove(l)
    fac.default_value = 0.0

    x, y = old.location.x + 250, old.location.y - 350
    uvn = nodes.new("ShaderNodeUVMap")
    uvn.name = uvn.label = f"{PREFIX} UV"
    uvn.uv_map = "TattooUV"
    uvn.location = (x - 700, y)

    shade = nodes.new("ShaderNodeTexImage")
    shade.name = shade.label = f"{PREFIX} shade"
    shade.image = shade_img
    shade.location = (x - 450, y)

    mask = nodes.new("ShaderNodeTexImage")
    mask.name = mask.label = f"{PREFIX} mask"
    mask.image = mask_img
    mask.location = (x - 450, y - 300)

    # shade map stores (glyph colour / surrounding skin) / 2
    x2 = nodes.new("ShaderNodeVectorMath")
    x2.name = x2.label = f"{PREFIX} x2"
    x2.operation = "SCALE"
    x2.inputs["Scale"].default_value = 2.0
    x2.location = (x - 180, y)

    mix = nodes.new("ShaderNodeMix")
    mix.name = mix.label = f"{PREFIX} multiply"
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.clamp_result = True
    mix.location = (x + 50, y + 200)

    links.new(uvn.outputs["UV"], shade.inputs["Vector"])
    links.new(uvn.outputs["UV"], mask.inputs["Vector"])
    links.new(shade.outputs["Color"], x2.inputs[0])
    links.new(mask.outputs["Color"], socket(mix, "Factor", "VALUE"))
    links.new(old.outputs["Color"], socket(mix, "A", "RGBA"))
    links.new(x2.outputs["Vector"], socket(mix, "B", "RGBA"))
    links.new(socket(mix, "Result", "RGBA", out=True), base)
    print("Game tattoos applied to", BODY_NAME)


main()
