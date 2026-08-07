"""Second-order smoothing.

A mass on a spring, with the far end of the spring pinned to the target. Because
it carries velocity as state it can overshoot, oscillate and anticipate, none of
which a plain lerp can do - a lerp only ever decelerates towards the target.

    y + k1*(dy/dt) + k2*(d2y/dt2)  =  x + k3*(dx/dt)

Works on floats and on Vector2s alike; every operation used here is defined for
both.
"""

import math


def _clone(value):
    return value + value * 0        # a copy for Vector2, a no-op for floats


class SecondOrder:
    """f - frequency in Hz, how fast it responds.
    z - damping: 0 rings forever, <1 overshoots then settles, 1 is the fastest
        approach with no overshoot at all, >1 is sluggish.
    r - response: 0 eases in slowly, 1 reacts the instant the input does,
        >1 overshoots, <0 moves the wrong way first (anticipation).
    """

    def __init__(self, f, z, r, initial):
        w = 2 * math.pi * f
        self.k1 = z / (math.pi * f)
        self.k2 = 1 / (w * w)
        self.k3 = r * z / w

        self.reset(initial)

    def reset(self, value):
        self.x_prev = _clone(value)
        self.y = _clone(value)
        self.yd = value * 0         # zero of the right type

    def update(self, dt, x, xd=None):
        if dt <= 0:
            return self.y

        if xd is None:
            xd = (x - self.x_prev) / dt
            self.x_prev = _clone(x)

        # This is explicit integration, so a large dt does not merely lose
        # accuracy - it diverges. Raising k2 (the mass term) keeps it stable.
        k2 = max(self.k2, dt * dt / 2 + dt * self.k1 / 2, dt * self.k1)

        self.y = self.y + self.yd * dt
        self.yd = self.yd + (x + self.k3 * xd - self.y - self.k1 * self.yd) * (dt / k2)

        return self.y
