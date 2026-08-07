import pygame as pg

import cgg

SPEED = 650         # pixels per second, on top of whatever the ship was doing
LIFETIME = 1.1      # seconds before it expires on its own
RADIUS = 3


class Bullet:
    def __init__(self, pos, direction, inherited_vel):
        self.pos = pg.Vector2(pos)
        self.prev = pg.Vector2(pos)
        self.vel = direction * SPEED + inherited_vel
        self.life = LIFETIME
        self.radius = RADIUS

    @property
    def dead(self):
        return self.life <= 0

    def update(self, dt):
        self.prev = pg.Vector2(self.pos)
        self.pos += self.vel * dt
        self.life -= dt

    def draw(self, surface, camera):
        cgg.draw_circle(surface, 'white', camera.to_screen(self.pos), RADIUS)
