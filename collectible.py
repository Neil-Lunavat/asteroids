import math

import pygame as pg

import cgg

RADIUS = 12
VALUE = 10
COLOR = (90, 240, 130)

PULSE_SPEED = 4.0       # radians per second
PULSE_AMOUNT = 0.22     # fraction of the radius it breathes by


class Collectible:
    def __init__(self, pos):
        self.pos = pg.Vector2(pos)
        self.radius = RADIUS
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    def draw(self, surface, camera):
        pulse = 1.0 + math.sin(self.t * PULSE_SPEED) * PULSE_AMOUNT
        cgg.draw_circle(
            surface, COLOR, camera.to_screen(self.pos), int(RADIUS * pulse), 2
        )
