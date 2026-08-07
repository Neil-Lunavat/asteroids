import pygame as pg

from dynamics import SecondOrder

# Gentler than the ship: mostly damped, with just enough overshoot to settle
# visibly when you stop.
FOLLOW_F, FOLLOW_Z, FOLLOW_R = 1.2, 0.85, 1.1

LEAD = 0.25         # seconds of velocity to aim ahead of the ship


class Camera:
    """Re-expresses world coordinates relative to itself, so the thing it is
    following ends up drawn near the centre of the screen.

    Nothing in the world knows the screen exists; this is the only place the
    two spaces meet.
    """

    def __init__(self, width, height):
        self.pos = pg.Vector2(0, 0)
        self.offset = pg.Vector2(width / 2, height / 2)
        self.smoother = SecondOrder(FOLLOW_F, FOLLOW_Z, FOLLOW_R, self.pos)

    def snap(self, target):
        self.pos = pg.Vector2(target)
        self.smoother.reset(self.pos)

    def follow(self, target, dt, velocity=None):
        goal = pg.Vector2(target)
        if velocity is not None:
            # Aim where the ship is going rather than where it has been.
            goal += velocity * LEAD
        self.pos = self.smoother.update(dt, goal)

    def to_screen(self, world_point):
        return pg.Vector2(world_point) - self.pos + self.offset
