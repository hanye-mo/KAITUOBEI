# -*- coding: utf-8 -*-
"""Blender 公共原语：MeshBuilder（bmesh 放样/回转/棱柱）+ 布尔/抽壳助手"""
import bpy
import bmesh
import math
from mathutils import Vector, Matrix

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import params as P


class MB:
    """网格构建器：先攒 (verts, faces)，一次 to_object。"""

    def __init__(self):
        self.verts = []
        self.faces = []

    def _add(self, pts, faces):
        base = len(self.verts)
        self.verts.extend(pts)
        self.faces.extend([[base + i for i in f] for f in faces])

    # ---- 放样（环闭合 + bridge）----
    def loft(self, rings, cap_start=True, cap_end=True):
        """rings: 逐站截面 3D 点列（各环点数相同、次序对应）"""
        bm = bmesh.new()
        ring_es = []
        for ring in rings:
            vs = [bm.verts.new(p) for p in ring]
            n = len(vs)
            es = [bm.edges.new((vs[i], vs[(i + 1) % n])) for i in range(n)]
            ring_es.append(es)
        for ea, eb in zip(ring_es, ring_es[1:]):
            bmesh.ops.bridge_loops(bm, edges=ea + eb)
        if cap_start:
            bmesh.ops.contextual_create(bm, geom=ring_es[0])
        if cap_end:
            bmesh.ops.contextual_create(bm, geom=ring_es[-1])
        me = bpy.data.meshes.new("tmp")
        bm.to_mesh(me)
        bm.free()
        self._add([v.co[:] for v in me.vertices], [list(p.vertices) for p in me.polygons])
        bpy.data.meshes.remove(me)
        return self

    # ---- 图元 ----
    def box(self, cx, cy, cz, sx, sy, sz):
        x0, x1 = cx - sx / 2, cx + sx / 2
        y0, y1 = cy - sy / 2, cy + sy / 2
        z0, z1 = cz - sz / 2, cz + sz / 2
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        f = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        self._add(v, f)
        return self

    def cyl(self, p0, p1, r, seg=P.SEG, caps=True):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0)
        L = d.length
        if L < 1e-9:
            return self
        d.normalize()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        xax = d.cross(up).normalized()
        yax = d.cross(xax).normalized()
        ring0 = [tuple(p0 + xax * (r * math.cos(2 * math.pi * i / seg)) + yax * (r * math.sin(2 * math.pi * i / seg))) for i in range(seg)]
        ring1 = [tuple(p1 + xax * (r * math.cos(2 * math.pi * i / seg)) + yax * (r * math.sin(2 * math.pi * i / seg))) for i in range(seg)]
        self.loft([ring0, ring1], cap_start=caps, cap_end=caps)
        return self

    def sphere(self, c, r, nu=P.SEG, nv=12):
        c = Vector(c)
        verts, faces = [], []
        for j in range(1, nv):
            phi = math.pi * j / nv
            for i in range(nu):
                th = 2 * math.pi * i / nu
                verts.append(tuple(c + r * Vector((math.sin(phi) * math.cos(th), math.sin(phi) * math.sin(th), math.cos(phi)))))
        top = tuple(c + Vector((0, 0, r)))
        bot = tuple(c + Vector((0, 0, -r)))
        base = len(self.verts)
        allv = [top] + verts + [bot]
        self._add(allv, [])
        b0 = base
        for j in range(nv - 2):
            for i in range(nu):
                a = b0 + 1 + j * nu + i
                b = b0 + 1 + j * nu + (i + 1) % nu
                cc = b0 + 1 + (j + 1) * nu + i
                dd = b0 + 1 + (j + 1) * nu + (i + 1) % nu
                self.faces.append([a, b, dd, cc])
        for i in range(nu):
            self.faces.append([b0, b0 + 1 + (i + 1) % nu, b0 + 1 + i])
            self.faces.append([b0 + 1 + (nv - 2) * nu + i, b0 + 1 + (nv - 2) * nu + (i + 1) % nu, b0 + 1 + (nv - 1) * nu])
        return self

    def prism_xz(self, profile, y0, y1):
        """XZ 剖面多边形沿 Y 拉伸（profile: [(x,z)] CCW）"""
        r0 = [(x, y0, z) for (x, z) in profile]
        r1 = [(x, y1, z) for (x, z) in profile]
        self.loft([r0, r1], cap_start=True, cap_end=True)
        return self

    def tube_path(self, pts, r, seg=P.SEG, first_bead=True):
        """折线路径圆柱链（节点自动搭接；first_bead=False 时不加首端球，须由既有球体覆盖开口）"""
        for i in range(len(pts) - 1):
            self.cyl(pts[i], pts[i + 1], r, seg, caps=True)   # 闭合壳：避免节点重合开口环（EXACT 毒药）
        if first_bead:
            self.sphere(pts[0], r)
        self.sphere(pts[-1], r)
        for p in pts[1:-1]:
            self.sphere(p, r)
        return self


def to_object(mb, name, coll, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in mb.verts]
    for f in mb.faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass                                   # 重复面/退化面跳过
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)   # 统一外向绕序（EXACT 布尔依赖）
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


# ---------- 修改器助手 ----------

def _apply_mod(ob, mod_name):
    with bpy.context.temp_override(active_object=ob, object=ob,
                                   selected_editable_objects=[ob], selected_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=mod_name)


def boolean(ob, tool, op='UNION'):
    md = ob.modifiers.new("bool", 'BOOLEAN')
    md.operation = op
    md.solver = 'EXACT'
    md.object = tool
    _apply_mod(ob, md.name)
    bpy.data.objects.remove(tool, do_unlink=True)
    return ob


def solidify(ob, thickness):
    md = ob.modifiers.new("sol", 'SOLIDIFY')
    md.thickness = thickness
    _apply_mod(ob, md.name)
    return ob


def bbox_of(ob):
    ws = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    mn = [min(w[i] for w in ws) for i in range(3)]
    mx = [max(w[i] for w in ws) for i in range(3)]
    return mn, mx


def union_bbox(objs):
    mns, mxs = [], []
    for ob in objs:
        mn, mx = bbox_of(ob)
        mns.append(mn)
        mxs.append(mx)
    return ([min(m[i] for m in mns) for i in range(3)],
            [max(m[i] for m in mxs) for i in range(3)])
