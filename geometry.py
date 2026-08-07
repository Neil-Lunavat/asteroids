"""Geometry helpers the game needs that are not part of the CGG syllabus.

Nothing in here is coursework - it is collision detection, hull generation and
area maths that the game happens to require. Syllabus algorithms live in cgg.py.
"""

import math

import pygame as pg

EPSILON = 1e-9


def polygon_area(points):
    """Shoelace formula. Sum the cross products of consecutive vertex pairs;
    the parts outside the polygon cancel out and twice the area is left over.
    """
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def polygon_centre(points):
    centre = pg.Vector2(0, 0)
    for p in points:
        centre += p
    return centre / len(points)


def convex_hull(points):
    """Andrew's monotone chain.

    Sort by x, then sweep left-to-right building the lower boundary and
    right-to-left building the upper one. A vertex survives only while it keeps
    turning the same way; the moment it would dent inwards it gets popped, so
    what remains is the outline with every concave point removed.
    """
    pts = sorted({(round(p[0], 6), round(p[1], 6)) for p in points})
    if len(pts) < 3:
        return [pg.Vector2(p) for p in pts]

    def turn(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return [pg.Vector2(p) for p in lower[:-1] + upper[:-1]]


def segment_intersect(a1, a2, b1, b2):
    """Where do segments a1->a2 and b1->b2 cross?

    Returns (t, u) with t the fraction along a and u the fraction along b, or
    None if they do not meet.
    """
    r = a2 - a1
    s = b2 - b1

    denom = r.x * s.y - r.y * s.x
    if abs(denom) < EPSILON:
        return None                     # parallel or degenerate

    d = b1 - a1
    t = (d.x * s.y - d.y * s.x) / denom
    u = (d.x * r.y - d.y * r.x) / denom

    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t, u
    return None


def _edge_normals(poly):
    """The candidate separating axes of a convex polygon: one perpendicular per
    edge, normalised so overlaps measured on different axes are comparable."""
    axes = []
    for i in range(len(poly)):
        edge = poly[(i + 1) % len(poly)] - poly[i]
        if edge.length_squared() < EPSILON:
            continue
        axes.append(pg.Vector2(-edge.y, edge.x).normalize())
    return axes


def _project(poly, axis):
    values = [axis.dot(p) for p in poly]
    return min(values), max(values)


def sat_collide(poly_a, poly_b):
    """Separating Axis Theorem. Returns the minimum translation vector that
    pushes poly_a clear of poly_b, or None if they are not touching.

    Both polygons must be convex.

    Project both shapes onto every edge normal of both. If any axis shows a gap
    between the two projections, that axis separates them and they cannot be
    touching, so we stop immediately. If no axis has a gap they do overlap, and
    the axis with the SMALLEST overlap is the cheapest way out - that overlap,
    along that axis, is the exact shortest push that frees them.

    This is the part Diagonals cannot do. Its push direction comes from wherever
    the vertices happen to sit, so on a shallow face-to-face contact it can shove
    almost parallel to the touching surfaces, sliding the shapes along each other
    while leaving them overlapped. That is what getting stuck looked like.
    """
    best_overlap = math.inf
    best_axis = None

    for axis in _edge_normals(poly_a) + _edge_normals(poly_b):
        a_lo, a_hi = _project(poly_a, axis)
        b_lo, b_hi = _project(poly_b, axis)

        overlap = min(a_hi, b_hi) - max(a_lo, b_lo)
        if overlap <= 0:
            return None                 # found a gap, definitely not touching

        if overlap < best_overlap:
            best_overlap = overlap
            best_axis = axis

    if best_axis is None:
        return None

    # Aim the axis from b towards a, so the result always describes moving a.
    if (polygon_centre(poly_a) - polygon_centre(poly_b)).dot(best_axis) < 0:
        best_axis = -best_axis

    return best_axis * best_overlap


def segment_hits_polygon(a1, a2, poly):
    """Does the segment a1->a2 cross the polygon's outline anywhere?

    Used for bullets: testing the path travelled since last frame rather than
    the bullet's current position means a fast bullet cannot skip straight
    through a thin rock between one frame and the next.
    """
    for i in range(len(poly)):
        if segment_intersect(a1, a2, poly[i], poly[(i + 1) % len(poly)]) is not None:
            return True
    return False


def circles_overlap(pos_a, radius_a, pos_b, radius_b):
    """Cheap broad-phase test, so the expensive polygon check only runs on pairs
    that could plausibly be touching."""
    reach = radius_a + radius_b
    return (pos_a - pos_b).length_squared() <= reach * reach
