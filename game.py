import math
import random as rd

import pygame as pg

import cgg
import collectible as collectible_mod
import geometry
from asteroid import Asteroid
from bullet import Bullet
from camera import Camera
from collectible import Collectible
from player import Player

WIDTH, HEIGHT = 800, 600
BG = (25, 25, 25)

MENU, PLAYING, DEAD = 'MENU', 'PLAYING', 'DEAD'

TARGET_ASTEROIDS = 12
SPAWN_RADIUS = 750          # just beyond the corner of the view
DESPAWN_RADIUS = 1500
SPAWN_SIZE = (30, 100)

STARTING_LIVES = 3
INVULN_TIME = 2.0

SOLVER_PASSES = 3           # position relaxation iterations per frame

PICKUP_RANGE = (350, 650)   # how far from the player a new one appears
INDICATOR_MARGIN = 34

STAR_COUNT = 170


class Game:
    def __init__(self):
        pg.init()
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption("Asteroids")
        self.clock = pg.time.Clock()

        self.font = pg.font.Font(None, 30)
        self.font_big = pg.font.Font(None, 64)

        # Darkens the drifting field so the menu text stays readable over it.
        self.dim = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        self.dim.fill((8, 10, 14, 195))

        self.camera = Camera(WIDTH, HEIGHT)
        self.stars = [
            (rd.randrange(WIDTH), rd.randrange(HEIGHT), rd.randint(55, 170))
            for _ in range(STAR_COUNT)
        ]

        self.highscore = 0
        self.state = MENU
        self.running = True
        self.reset()

    def reset(self):
        self.player = Player(0, 0)
        self.bullets = []
        self.asteroids = []
        self.score = 0
        self.lives = STARTING_LIVES
        self.invuln = 0.0

        while len(self.asteroids) < TARGET_ASTEROIDS:
            pos = pg.Vector2(rd.uniform(-900, 900), rd.uniform(-700, 700))
            if pos.length() < 250:      # keep the area around the player clear
                continue
            self.asteroids.append(Asteroid(pos, rd.uniform(*SPAWN_SIZE)))

        self.collectible = None
        self.place_collectible()
        self.camera.snap(self.player.pos)

    # ------------------------------------------------------------- input ----

    def handle_events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    self.running = False
                elif event.key == pg.K_SPACE and self.state in (MENU, DEAD):
                    self.reset()
                    self.state = PLAYING

    def read_input(self, dt):
        keys = pg.key.get_pressed()

        self.player.turn(keys[pg.K_d] - keys[pg.K_a], dt)
        self.player.set_thrust(keys[pg.K_w])

        if keys[pg.K_SPACE] and self.player.can_fire():
            self.player.note_fired()
            self.bullets.append(Bullet(
                self.player.muzzle(), self.player.facing(), self.player.vel
            ))

    # ------------------------------------------------------------ spawning --

    def spawn_asteroid(self):
        """Drop a rock on a ring outside the view, aimed to drift across it."""
        edge = pg.Vector2(1, 0).rotate(rd.uniform(0, 360))
        pos = self.player.pos + edge * SPAWN_RADIUS

        # Aim near the player, but not exactly at them.
        aim = self.player.pos + pg.Vector2(
            rd.uniform(-250, 250), rd.uniform(-250, 250)
        )
        heading = aim - pos
        if heading.length_squared() == 0:
            heading = -edge

        vel = heading.normalize() * rd.uniform(30, 90)
        self.asteroids.append(Asteroid(pos, rd.uniform(*SPAWN_SIZE), vel))

    def manage_field(self):
        self.asteroids = [
            a for a in self.asteroids
            if (a.pos - self.player.pos).length() < DESPAWN_RADIUS
        ]
        while len(self.asteroids) < TARGET_ASTEROIDS:
            self.spawn_asteroid()

    def place_collectible(self):
        direction = pg.Vector2(1, 0).rotate(rd.uniform(0, 360))
        self.collectible = Collectible(
            self.player.pos + direction * rd.uniform(*PICKUP_RANGE)
        )

    # ---------------------------------------------------------- collisions --

    def bullets_vs_asteroids(self):
        spawned = []
        dead_bullets = set()
        dead_asteroids = set()

        for bi, b in enumerate(self.bullets):
            for ai, a in enumerate(self.asteroids):
                if ai in dead_asteroids:
                    continue

                # Broad phase over the whole path travelled this frame.
                midpoint = (b.prev + b.pos) / 2
                reach = (b.pos - b.prev).length() / 2 + b.radius
                if not geometry.circles_overlap(midpoint, reach, a.pos, a.radius):
                    continue

                if not geometry.segment_hits_polygon(b.prev, b.pos, a.world_points()):
                    continue

                dead_bullets.add(bi)
                dead_asteroids.add(ai)
                self.score += int(max(10, 2000 / a.radius))
                spawned.extend(a.split())
                break

        self.bullets = [b for i, b in enumerate(self.bullets) if i not in dead_bullets]
        self.asteroids = [a for i, a in enumerate(self.asteroids) if i not in dead_asteroids]
        self.asteroids.extend(spawned)

    def asteroids_vs_asteroids(self):
        contacts = []
        for i in range(len(self.asteroids)):
            for j in range(i + 1, len(self.asteroids)):
                a, b = self.asteroids[i], self.asteroids[j]

                if not geometry.circles_overlap(a.pos, a.radius, b.pos, b.radius):
                    continue
                if geometry.sat_collide(a.world_points(), b.world_points()) is None:
                    continue

                contacts.append((a, b))

        # One impulse per contact per frame. A rock touching two others would
        # otherwise get kicked twice and shoot off.
        for a, b in contacts:
            self.exchange_momentum(a, b)

        # Then push everything apart repeatedly: separating A from B can shove
        # it straight back into C, so one pass is not enough inside a cluster.
        for _ in range(SOLVER_PASSES):
            settled = True
            for a, b in contacts:
                push = geometry.sat_collide(a.world_points(), b.world_points())
                if push is None:
                    continue

                total = a.mass + b.mass
                a.pos += push * (b.mass / total)
                b.pos -= push * (a.mass / total)
                settled = False

            if settled:
                break

    @staticmethod
    def exchange_momentum(a, b):
        """Elastic collision along the line joining the two centres."""
        normal = b.pos - a.pos
        if normal.length_squared() == 0:
            return
        normal = normal.normalize()

        approach = (a.vel - b.vel).dot(normal)
        if approach <= 0:
            return                      # already moving apart, leave them alone

        impulse = 2 * approach / (a.mass + b.mass)
        a.vel -= normal * impulse * b.mass
        b.vel += normal * impulse * a.mass

    def player_vs_asteroids(self):
        if self.invuln > 0:
            return

        for a in self.asteroids:
            if not geometry.circles_overlap(
                self.player.pos, self.player.radius, a.pos, a.radius
            ):
                continue
            if geometry.sat_collide(
                self.player.world_points(), a.world_points()
            ) is None:
                continue

            self.lose_life()
            return

    def player_vs_collectible(self):
        if self.collectible is None:
            return
        if geometry.circles_overlap(
            self.player.pos, self.player.radius,
            self.collectible.pos, self.collectible.radius,
        ):
            self.score += collectible_mod.VALUE
            self.place_collectible()

    def lose_life(self):
        self.lives -= 1
        self.player.vel = pg.Vector2(0, 0)
        self.invuln = INVULN_TIME

        if self.lives <= 0:
            self.highscore = max(self.highscore, self.score)
            self.state = DEAD

    # ------------------------------------------------------------ updating --

    def update(self, dt):
        if self.state == PLAYING:
            self.update_playing(dt)
        else:
            # Keep the field drifting behind the menu so it is never a still image.
            for a in self.asteroids:
                a.update(dt)
            self.asteroids_vs_asteroids()
            self.manage_field()

    def update_playing(self, dt):
        self.invuln = max(0.0, self.invuln - dt)

        self.read_input(dt)
        self.player.update(dt)

        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if not b.dead]

        for a in self.asteroids:
            a.update(dt)
        self.collectible.update(dt)

        self.bullets_vs_asteroids()
        self.asteroids_vs_asteroids()
        self.player_vs_asteroids()
        self.player_vs_collectible()

        self.manage_field()
        self.camera.follow(self.player.pos, dt, self.player.vel)

    # ------------------------------------------------------------ drawing ---

    def draw_stars(self):
        for x, y, brightness in self.stars:
            cgg.draw_circle(self.screen, (brightness,) * 3, (x, y), 1)

    def draw_indicator(self, target):
        """Arrow pinned to the edge of the window pointing at something that is
        currently off-screen. Hidden once the target is actually visible."""
        spot = self.camera.to_screen(target)
        on_screen = (
            INDICATOR_MARGIN <= spot.x <= WIDTH - INDICATOR_MARGIN
            and INDICATOR_MARGIN <= spot.y <= HEIGHT - INDICATOR_MARGIN
        )
        if on_screen:
            return

        centre = pg.Vector2(WIDTH / 2, HEIGHT / 2)
        offset = spot - centre
        if offset.length_squared() == 0:
            return

        # Walk out along the direction until it hits the window edge.
        half_w = WIDTH / 2 - INDICATOR_MARGIN
        half_h = HEIGHT / 2 - INDICATOR_MARGIN
        scale = min(
            half_w / abs(offset.x) if abs(offset.x) > 1e-6 else math.inf,
            half_h / abs(offset.y) if abs(offset.y) > 1e-6 else math.inf,
        )
        edge = centre + offset * scale

        angle = pg.Vector2(1, 0).angle_to(offset)
        arrow = [pg.Vector2(11, 0), pg.Vector2(-7, -7), pg.Vector2(-7, 7)]
        cgg.draw_polygon(
            self.screen, collectible_mod.COLOR,
            [edge + p.rotate(angle) for p in arrow], width=2,
        )

    def draw_hud(self):
        score = self.font.render(str(self.score), True, 'white')
        self.screen.blit(score, (WIDTH - score.get_width() - 20, 20))

        for i in range(self.lives):
            x = 24 + i * 26
            cgg.draw_polygon(self.screen, 'white', [
                (x, 18), (x - 7, 34), (x + 7, 34),
            ], width=2)

    def draw_centred(self, text, y, font=None, color='white'):
        surf = (font or self.font).render(text, True, color)
        self.screen.blit(surf, (WIDTH / 2 - surf.get_width() / 2, y))

    def draw_overlay(self):
        if self.state in (MENU, DEAD):
            self.screen.blit(self.dim, (0, 0))

        if self.state == MENU:
            self.draw_centred("ASTEROIDS", 210, self.font_big)
            self.draw_centred("PRESS SPACE TO START", 300)
            self.draw_centred("A / D  turn      W  thrust      SPACE  fire", 340,
                              color=(150, 150, 150))
        elif self.state == DEAD:
            self.draw_centred("GAME OVER", 210, self.font_big)
            self.draw_centred("SCORE  %d" % self.score, 300)
            self.draw_centred("HIGHSCORE  %d" % self.highscore, 330,
                              color=(150, 150, 150))
            self.draw_centred("PRESS SPACE TO RESTART", 380)

        if self.highscore and self.state == PLAYING:
            best = self.font.render("BEST %d" % self.highscore, True, (120, 120, 120))
            self.screen.blit(best, (WIDTH - best.get_width() - 20, 48))

    def draw(self):
        self.screen.fill(BG)
        self.draw_stars()

        for a in self.asteroids:
            a.draw(self.screen, self.camera)

        if self.state == PLAYING:
            for b in self.bullets:
                b.draw(self.screen, self.camera)

            self.collectible.draw(self.screen, self.camera)
            self.draw_indicator(self.collectible.pos)

            # Blink while invulnerable.
            if self.invuln <= 0 or int(self.invuln * 10) % 2 == 0:
                self.player.draw(self.screen, self.camera, BG)

            self.draw_hud()

        self.draw_overlay()
        pg.display.flip()

    def run(self):
        while self.running:
            dt = min(self.clock.tick(60) / 1000, 0.05)
            self.handle_events()
            self.update(dt)
            self.draw()
        pg.quit()


if __name__ == "__main__":
    Game().run()
