import math
import random as rd

import pygame as pg

import cgg
import geometry

SPEED_RANGE = (20, 70)      # pixels per second
SPIN_RANGE = (-40, 40)      # degrees per second

SPLIT_THRESHOLD = 60        # only asteroids larger than this break apart
AREA_RETAINED = 0.9         # children together keep 90% of the parent's area
MIN_CHILD_RADIUS = 14       # anything smaller than this is just dust, drop it


class Asteroid:
    def __init__(self, center, size, vel=None):
        self.pos = pg.Vector2(center)

        if vel is None:
            # Constant velocity, randomised once. No drag - it is space, and the
            # variety the player sees comes from parallax, not from jitter.
            heading = rd.uniform(0, 360)
            vel = pg.Vector2(1, 0).rotate(heading) * rd.uniform(*SPEED_RANGE)
        self.vel = pg.Vector2(vel)

        self.angle = rd.uniform(0, 360)
        self.spin = rd.uniform(*SPIN_RANGE)
        self.color = 'white'

        self.points = self._generate(size)
        self._measure()

    @staticmethod
    def _generate(size):
        """Scatter points in a rough disc, then keep only the hull. The dents
        vanish and what is left is guaranteed convex."""
        while True:
            raw = []
            for _ in range(rd.randint(7, 12)):
                angle = rd.uniform(0, 2 * math.pi)
                r = rd.uniform(size * 0.6, size)
                raw.append(pg.Vector2(math.cos(angle) * r, math.sin(angle) * r))

            hull = geometry.convex_hull(raw)
            if len(hull) >= 3:
                return hull

    def _measure(self):
        self.radius = max(p.length() for p in self.points)
        self.area = geometry.polygon_area(self.points)
        self.mass = self.area

    def scale_to_area(self, target):
        """Uniform scale about the centre. Scaling by k multiplies area by k*k,
        so k is the square root of the ratio we want."""
        current = geometry.polygon_area(self.points)
        if current <= 0:
            return
        k = math.sqrt(target / current)
        self.points = [p * k for p in self.points]
        self._measure()

    def split(self):
        if self.radius <= SPLIT_THRESHOLD:
            return []

        count = rd.choice((2, 3))
        budget = self.area * AREA_RETAINED

        weights = [rd.uniform(0.75, 1.25) for _ in range(count)]
        share = budget / sum(weights)

        children = []
        for w in weights:
            child = Asteroid(self.pos, self.radius, self.vel)
            child.scale_to_area(w * share)
            if child.radius >= MIN_CHILD_RADIUS:
                children.append(child)

        if not children:
            return []

        # Place the children on a ring, evenly spaced. Adjacent centres on a
        # ring of radius R sit 2*R*sin(pi/n) apart, so picking R from the
        # largest child guarantees none of them start life inside each other -
        # which is what made splitting explode into a jittering mess.
        n = len(children)
        biggest = max(c.radius for c in children)
        ring = biggest / math.sin(math.pi / n) * 1.15 if n > 1 else 0.0

        base = rd.uniform(0, 360)
        for i, child in enumerate(children):
            outward = pg.Vector2(1, 0).rotate(base + i * 360 / n)
            child.pos = self.pos + outward * ring
            child.vel = self.vel + outward * rd.uniform(40, 90)

        return children

    def update(self, dt):
        self.pos += self.vel * dt
        self.angle += self.spin * dt

    def world_points(self):
        return [self.pos + p.rotate(self.angle) for p in self.points]

    def draw(self, surface, camera):
        points = [camera.to_screen(p) for p in self.world_points()]
        if self.radius <= SPLIT_THRESHOLD:
            # Too small to break apart - one hit and it is gone. Filling it in
            # tells the player that at a glance.
            cgg.draw_polygon(surface, (*pg.Color(self.color)[:3], 55), points, width=0)
        cgg.draw_polygon(surface, self.color, points, width=5)
