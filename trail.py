"""Thruster ribbon.

Nodes are stored in WORLD space, not in the ship's model space. That is the
whole trick: a trail held in model space would swing around rigidly whenever the
ship turned, whereas world-space nodes stay where they were emitted, so the
ribbon becomes a record of where the ship actually went.
"""

from collections import deque

import pygame as pg

import cgg

LIFE = 0.45         # seconds before a node disappears
MIN_STEP = 3.0      # only emit after moving this far, so hovering does not pile up
WIDTH = 5           # width at the head, tapering to 1 at the tail
HOT = pg.Color(255, 196, 104)


class Trail:
    def __init__(self):
        self.nodes = deque()        # newest first: [world_pos, age]

    def emit(self, pos):
        if self.nodes and (pos - self.nodes[0][0]).length() < MIN_STEP:
            return
        self.nodes.appendleft([pg.Vector2(pos), 0.0])

    def update(self, dt):
        for node in self.nodes:
            node[1] += dt

        # Age nodes out rather than capping the count, so the ribbon dissolves
        # from the tail forward when thrust stops instead of hanging in the air.
        while self.nodes and self.nodes[-1][1] >= LIFE:
            self.nodes.pop()

    def draw(self, surface, camera, background):
        if len(self.nodes) < 2:
            return

        bg = pg.Color(background)
        points = [camera.to_screen(node[0]) for node in self.nodes]

        for i in range(len(points) - 1):
            t = min(1.0, self.nodes[i][1] / LIFE)

            # pygame has no per-vertex alpha, but the background is a flat
            # colour, so lerping towards it looks identical and costs nothing.
            cgg.draw_line(
                surface, HOT.lerp(bg, t),
                points[i], points[i + 1],
                max(1, int(WIDTH * (1.0 - t))),
            )
