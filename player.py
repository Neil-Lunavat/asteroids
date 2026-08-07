import math

import pygame as pg

import cgg
from dynamics import SecondOrder
from trail import Trail

TURN_SPEED = 200    # degrees per second
THRUST = 400        # pixels per second squared
DRAG = 0.6          # exponential decay rate -> terminal speed is THRUST / DRAG
FIRE_COOLDOWN = 0.18

# Underdamped with a response above 1, so the nose overshoots and settles on
# every turn instead of arriving politely.
ROT_F, ROT_Z, ROT_R = 2.5, 0.6, 1.4

# Recoil is a purely visual offset along the ship's own axis - self.pos never
# moves. Out fast, home gently, and finished well inside FIRE_COOLDOWN so held
# fire never restarts the curve part-way and pops.
#
# A spring would be the house style here, but the wrong tool: SecondOrder clamps
# k2 to stay stable, and that clamp binds above f = 1/(4*pi*dt*z), only ~4.8Hz at
# 60fps. Settling a recoil this short needs f ~7, so the spring would quietly run
# softer and slower than asked - and it only ever asymptotes, so "done before the
# next shot" could not be guaranteed. A timed curve gives an exact duration.
RECOIL_DIST = 12.0       # pixels at the furthest point of the kick
RECOIL_OUT = 0.035      # seconds to snap back
RECOIL_IN = 0.25        # seconds to ease home


class Player:
    def __init__(self, x, y):
        self.pos = pg.Vector2(x, y)
        self.vel = pg.Vector2(0, 0)
        self.size = 20
        self.radius = self.size
        self.cooldown = 0.0

        # target_angle is what input moves; angle is what gets drawn, chasing it
        # through the spring below. Note target_angle is never wrapped to
        # 0-360 - it just accumulates - which is what stops the smoother from
        # spinning the long way round when it would cross zero.
        self.target_angle = -90     # -90 degrees == pointing up the screen
        self.angle = self.target_angle
        self.rotation = SecondOrder(ROT_F, ROT_Z, ROT_R, self.target_angle)
        self.thrusting = False

        # Starts finished, so the first frame draws no offset.
        self.recoil_t = RECOIL_OUT + RECOIL_IN

        # Model space: nose along +x, so rotating by `angle` aims the whole ship.
        self.model = [
            pg.Vector2(self.size, 0),
            pg.Vector2(-self.size / 2, -self.size / 2),
            pg.Vector2(-self.size / 2, self.size / 2),
        ]

        self.thrusters = [
            pg.Vector2(-self.size / 2, -self.size * 0.38),
            pg.Vector2(-self.size / 2, self.size * 0.38),
        ]
        self.trails = [Trail() for _ in self.thrusters]

    def turn(self, amount, dt):
        self.target_angle += amount * TURN_SPEED * dt

    def set_thrust(self, on):
        self.thrusting = bool(on)

    def facing(self):
        return pg.Vector2(1, 0).rotate(self.angle)

    def muzzle(self):
        return self.pos + self.facing() * self.size

    def can_fire(self):
        return self.cooldown <= 0

    def note_fired(self):
        self.cooldown = FIRE_COOLDOWN
        self.recoil_t = 0.0

    def recoil_offset(self):
        """Signed displacement along the nose axis; negative is backwards.

        Two pieces: 1-(1-u)^2 decelerates into the peak, then (1-u)^3 leaves it
        fast and arrives with zero velocity, which is what reads as easing home.
        """
        t = self.recoil_t
        if t >= RECOIL_OUT + RECOIL_IN:
            return 0.0

        if t < RECOIL_OUT:
            u = t / RECOIL_OUT
            return -RECOIL_DIST * (1 - (1 - u) ** 2)

        u = (t - RECOIL_OUT) / RECOIL_IN
        return -RECOIL_DIST * (1 - u) ** 3

    def visual_pos(self):
        """Where the ship is drawn. self.pos is where it actually is; the two
        differ only mid-recoil, and nothing that collides or spawns ever uses
        this one. Storing an offset rather than the position it fired from is
        what lets flying and recoiling compose without a special case - the
        offset simply decays to zero on top of wherever the ship has got to.

        It follows the current facing, so it stays behind the nose in a turn.
        """
        return self.pos + self.facing() * self.recoil_offset()

    def update(self, dt):
        self.cooldown -= dt
        self.recoil_t += dt
        self.angle = self.rotation.update(dt, self.target_angle)

        # Thrust follows the smoothed angle, not the target, so the ship's
        # heading lags the input slightly. That lag is what reads as weight.
        acc = self.facing() * THRUST if self.thrusting else pg.Vector2(0, 0)

        # Semi-implicit Euler: velocity first, then position using the new velocity.
        self.vel += acc * dt
        self.vel *= math.exp(-DRAG * dt)
        self.pos += self.vel * dt

        # Emitted from the drawn position, not the true one, or the flames
        # detach from the engines for as long as the hull is displaced.
        origin = self.visual_pos()
        for trail, mount in zip(self.trails, self.thrusters):
            if self.thrusting:
                trail.emit(origin + mount.rotate(self.angle))
            trail.update(dt)

    def points_at(self, origin):
        return [origin + p.rotate(self.angle) for p in self.model]

    def world_points(self):
        return self.points_at(self.pos)     # the true hull, for collision

    def draw(self, surface, camera, background):
        for trail in self.trails:
            trail.draw(surface, camera, background)

        points = [camera.to_screen(p) for p in self.points_at(self.visual_pos())]
        cgg.draw_polygon(surface, 'white', points, width=5)
