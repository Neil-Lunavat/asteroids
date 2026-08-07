"""Computer Graphics & Gaming - hand-coded algorithms.

Every drawing call in the game routes through this module. Right now each
function just forwards to pygame; as the course assignments land, the bodies get
replaced with the real algorithms (DDA, Bresenham, midpoint, scan-line fill,
Cohen-Sutherland...) and the rest of the game does not change.
"""

import pygame as pg


def draw_line(surface, color, a, b, width=1):
    pg.draw.line(surface, color, a, b, width)


def draw_polygon(surface, color, points, width=1):
    if pg.Color(color).a < 255:
        # Opaque surfaces ignore the alpha, so draw onto a transparent layer the
        # size of the polygon's bounding box and blit that over instead.
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        off = pg.Vector2(min(xs), min(ys))
        layer = pg.Surface(
            (int(max(xs) - off.x) + 2, int(max(ys) - off.y) + 2), pg.SRCALPHA
        )
        pg.draw.polygon(layer, color, [pg.Vector2(p) - off for p in points], width)
        surface.blit(layer, off)
        return
    pg.draw.polygon(surface, color, points, width)


def draw_circle(surface, color, center, radius, width=1):
    pg.draw.circle(surface, color, center, radius, width)
