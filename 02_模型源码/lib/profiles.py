# -*- coding: utf-8 -*-
"""截面/几何函数（纯 Python，可脱离 Blender 自检）
坐标系约定：放样沿 +X，截面在 YZ 平面（y=展向，z=垂向）。
"""
import math

# ---------- 基础 ----------

def interp(xs, ys, x):
    """线性插值（越界钳位）"""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])
    return ys[-1]


def arch_pts(s, h, n=24, p=2.2, q=0.75, clamp=None):
    """超椭圆拱顶截面（底平 z=0），闭合多边形，CCW，固定 2n 点。
    顶弧 z(y)=h*(1-(|y|/s)^p)^q；clamp 不为 None 时取 min(z, clamp)。"""
    pts = []
    for i in range(n + 1):                      # 顶弧：右下角 → 顶 → 左下角
        yy = s * (1.0 - 2.0 * i / n)
        zz = 0.0
        if s > 1e-9 and abs(yy) < s:
            zz = h * (1.0 - (abs(yy) / s) ** p) ** q
        if clamp is not None:
            zz = min(zz, clamp)
        pts.append((yy, zz))
    for i in range(1, n):                       # 底边内部点：左 → 右
        pts.append((-s + 2.0 * s * i / n, 0.0))
    return pts


def circle_like(src, r, cz):
    """把凸截面 src（CCW）按极角映射到圆（半径 r，圆心 y=0,z=cz），点数不变。"""
    ys = [p[0] for p in src]
    zs = [p[1] for p in src]
    yc, zc = sum(ys) / len(ys), sum(zs) / len(zs)
    out = []
    for (y, z) in src:
        a = math.atan2(z - zc, y - yc)
        out.append((r * math.cos(a), cz + r * math.sin(a)))
    return out


def convex_offset(poly, d):
    """凸多边形（CCW）外法向偏移 d，返回新 CCW 多边形（相邻偏移线求交）。"""
    m = len(poly)
    lines = []
    for i in range(m):
        p1, p2 = poly[i], poly[(i + 1) % m]
        ex, ez = p2[0] - p1[0], p2[1] - p1[1]
        L = math.hypot(ex, ez)
        if L < 1e-12:
            continue
        nx, nz = ez / L, -ex / L                # CCW 外法向
        lines.append(((p1[0] + d * nx, p1[1] + d * nz), ex, ez))
    out = []
    for i in range(len(lines)):
        (ax, az), e1x, e1z = lines[i - 1]
        (bx, bz), e2x, e2z = lines[i]
        det = e1x * e2z - e1z * e2x
        if abs(det) < 1e-12:
            out.append((bx, bz))
            continue
        t = ((bx - ax) * e2z - (bz - az) * e2x) / det
        out.append((ax + t * e1x, az + t * e1z))
    return out


def convex_hull(points):
    """单调链凸包，输入 [(y,z)]，输出 CCW。"""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def clip_halfplane(poly, keep_positive, axis=0, eps=1e-9):
    """Sutherland–Hodgman 半平面裁剪：axis=0 按 y，keep_positive=True 保留 y>=0。"""

    def inside(p):
        v = p[axis]
        return v >= -eps if keep_positive else v <= eps

    def intersect(p1, p2):
        a, b = p1[axis], p2[axis]
        t = (0.0 - a) / (b - a)
        return tuple(p1[i] + t * (p2[i] - p1[i]) for i in range(len(p1)))

    out = []
    m = len(poly)
    for i in range(m):
        cur, nxt = poly[i], poly[(i + 1) % m]
        ci, ni = inside(cur), inside(nxt)
        if ci:
            out.append(cur)
        if ci != ni:
            out.append(intersect(cur, nxt))
    return out


def rotate_to_top(poly):
    """旋转点列使其从 z 最大（并列取 y 最大）的点开始，保证两半起点一致。"""
    k = max(range(len(poly)), key=lambda i: (poly[i][1], poly[i][0]))
    return poly[k:] + poly[:k]


def rotate_to_anchor(poly, anchor=(0.0, 0.5)):
    """旋转点列使其从最接近 anchor 的顶点开始（确定性，保证站间顶点对应关系稳定）"""
    k = min(range(len(poly)), key=lambda i: (poly[i][0] - anchor[0]) ** 2 + (poly[i][1] - anchor[1]) ** 2)
    return poly[k:] + poly[:k]


def resample(poly, n):
    """闭合多边形等弧长重采样为 n 点。"""
    m = len(poly)
    seg = []
    total = 0.0
    for i in range(m):
        p1, p2 = poly[i], poly[(i + 1) % m]
        L = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        seg.append(L)
        total += L
    out = []
    step = total / n
    target = 0.0
    acc = 0.0
    j = 0
    for k in range(n):
        target = k * step
        while acc + seg[j] < target and j < m - 1:
            acc += seg[j]
            j += 1
        t = (target - acc) / max(seg[j], 1e-12)
        p1, p2 = poly[j], poly[(j + 1) % m]
        out.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
    return out


def scaled_arch(s, h, peak, p=2.2, q=0.75, n=24):
    """等峰拱顶截面：底平 z=0，顶弧形状与原超椭圆一致但峰值缩放到 peak（h<=peak 时原样）"""
    pts = arch_pts(s, h, n=n, p=p, q=q)
    if h > 1e-9 and h > peak:
        f = peak / h
        pts = [(y, z * f) for (y, z) in pts]
    return pts


def arch_z_at(x, y, xs, ss, hs, peak, p=2.2, q=0.75):
    """等峰拱顶在站位 x、展向 y 处的表面高度"""
    s = interp(xs, ss, x)
    h = interp(xs, hs, x)
    z = h * (1.0 - (abs(y) / s) ** p) ** q if s > 1e-9 and abs(y) < s else 0.0
    f = min(1.0, peak / h) if h > 1e-9 else 1.0
    return z * f


def hex_rib(c, t):
    """六边形翼剖面（弦 c，厚 t），[(x,z)]，LE 在 x=0。"""
    return [(0.0, 0.0), (0.15 * c, t / 2), (0.55 * c, t / 2),
            (c, 0.0), (0.55 * c, -t / 2), (0.15 * c, -t / 2)]


def octagon(w, hgt, corner):
    """圆角矩形近似八角断面（XZ 平面，居中）。"""
    a, b = w / 2, hgt / 2
    return [(-a, -(b - corner)), (-a, b - corner), (-(a - corner), b), (a - corner, b),
            (a, b - corner), (a, -(b - corner)), (a - corner, -b), (-(a - corner), -b)]


def polygon_area(poly):
    a = 0.0
    m = len(poly)
    for i in range(m):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % m]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


# ---------- 自检（python lib/profiles.py） ----------
if __name__ == "__main__":
    import params as P
    ok = True
    print("=== profiles self test ===")
    for i in range(1, len(P.RM_X)):
        s, h = P.RM_S[i], P.RM_H[i]
        a = polygon_area(arch_pts(s, h, p=P.RM_SE_P, q=P.RM_SE_Q))
        ratio = a / (2 * s * h)
        flag = "OK" if 0.60 <= ratio <= 0.88 else "FAIL"
        ok &= (flag == "OK")
        print(f"RM station {i:2d} x={P.RM_X[i]:4d} s={s:4d} h={h:3d} area={a:9.1f} ratio={ratio:.3f} {flag}")
    for i in range(1, len(P.YR_X)):
        s, h = P.YR_S[i], P.YR_H[i]
        a = polygon_area(arch_pts(s, h, p=P.YR_SE_P, q=P.YR_SE_Q))
        ratio = a / (2 * s * h)
        flag = "OK" if 0.60 <= ratio <= 0.88 else "FAIL"
        ok &= (flag == "OK")
        print(f"YR station {i:2d} x={P.YR_X[i]:4d} s={s:4d} h={h:3d} area={a:9.1f} ratio={ratio:.3f} {flag}")
    # 凸包/裁剪/偏移/重采样冒烟测试
    poly = arch_pts(650, 523, p=P.RM_SE_P, q=P.RM_SE_Q)
    off = convex_offset(poly, 3.0)
    hz = convex_hull(poly)
    half = clip_halfplane(hz, True)
    rs = resample(rotate_to_top(half), 28)
    print(f"hull pts={len(hz)} half pts={len(half)} resample={len(rs)} offset0={off[0]}")
    ok &= len(rs) == 28 and len(off) == len(poly)
    print("RESULT:", "PASS" if ok else "FAIL")


def rotate_to_anchor(poly, anchor=(0.0, 0.5)):
    """旋转点列使其从最接近 anchor 的顶点开始（确定性，保证站间顶点对应关系稳定）"""
    k = min(range(len(poly)), key=lambda i: (poly[i][0] - anchor[0]) ** 2 + (poly[i][1] - anchor[1]) ** 2)
    return poly[k:] + poly[:k]
