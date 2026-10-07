"""Deterministic procedural soundtrack for "THE AWAKENED SCRIPT".

120 BPM (0.5 s/beat), A minor. Every cue time below mirrors a tween in index.html.
Output: audio/soundtrack.wav (44.1 kHz, 16-bit stereo, exactly 20.0 s).
"""
import os
import wave
import numpy as np

SR = 44100
DUR = 20.0
TAIL = 2.5
N = int((DUR + TAIL) * SR)
rng = np.random.default_rng(2020)

dry = np.zeros((2, N))
wet = np.zeros((2, N))


# ---------------------------------------------------------------- helpers
def T(n):
    return np.arange(n) / SR


def mid(n):
    return 440.0 * 2 ** ((n - 69) / 12.0)


def filt(x, lo=None, hi=None):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    g = np.ones_like(f)
    if hi:
        g = g / (1 + (f / hi) ** 4)
    if lo:
        g = g / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    return np.fft.irfft(X * g, n)


def lp_sweep(x, fc):
    a = (1 - np.exp(-2 * np.pi * np.asarray(fc) / SR)).tolist()
    xs = x.tolist()
    y = 0.0
    out = [0.0] * len(xs)
    for i in range(len(xs)):
        y += a[i] * (xs[i] - y)
        out[i] = y
    out = np.array(out)
    # second pass for 12 dB/oct
    y = 0.0
    xs = out.tolist()
    for i in range(len(xs)):
        y += a[i] * (xs[i] - y)
        out[i] = y
    return out


def place(sig, t, g=1.0, pan=0.0, send=0.0):
    i = int(round(t * SR))
    if i < 0 or i >= N:
        return
    s = sig[: N - i]
    l = g * np.cos((pan + 1) * np.pi / 4)
    r = g * np.sin((pan + 1) * np.pi / 4)
    dry[0, i:i + len(s)] += s * l
    dry[1, i:i + len(s)] += s * r
    if send > 0:
        wet[0, i:i + len(s)] += s * l * send
        wet[1, i:i + len(s)] += s * r * send


def place_sweep(sig, t, g, pan0, pan1, send=0.0):
    i = int(round(t * SR))
    s = sig[: N - i]
    p = np.linspace(pan0, pan1, len(s))
    l = g * np.cos((p + 1) * np.pi / 4)
    r = g * np.sin((p + 1) * np.pi / 4)
    dry[0, i:i + len(s)] += s * l
    dry[1, i:i + len(s)] += s * r
    if send > 0:
        wet[0, i:i + len(s)] += s * l * send
        wet[1, i:i + len(s)] += s * r * send


def chirp(f0, f1, dur):
    n = int(dur * SR)
    t = T(n)
    f = f0 * (f1 / f0) ** (t / dur)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def saw(f, n, harm=10):
    t = T(n)
    s = np.zeros(n)
    k = 1
    while k <= harm and f * k < SR / 2:
        s += np.sin(2 * np.pi * f * k * t) / k
        k += 1
    return s


def noise(n):
    return rng.standard_normal(n)


# ---------------------------------------------------------------- instruments
def kick(f0=160, f1=42, dur=0.45, tau=0.16):
    n = int(dur * SR)
    t = T(n)
    f = f1 + (f0 - f1) * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t / tau) * (1 - np.exp(-t / 0.0008))
    s += 0.25 * noise(n) * np.exp(-t / 0.004)
    return s


def clap():
    n = int(0.3 * SR)
    t = T(n)
    s = np.zeros(n)
    for off in (0.0, 0.011, 0.023):
        j = int(off * SR)
        s[j:] += noise(n - j) * np.exp(-t[: n - j] / 0.006)
    s += noise(n) * np.exp(-t / 0.09) * 0.7
    s = filt(s, lo=1200, hi=8000)
    s += 0.3 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05)
    return s


def hat(open_=False):
    n = int((0.22 if open_ else 0.07) * SR)
    t = T(n)
    return filt(noise(n), lo=7000) * np.exp(-t / (0.09 if open_ else 0.022))


def whoosh(dur, f0, f1, peak=0.5, power=2.0):
    n = int(dur * SR)
    t = T(n) / dur
    env = (t ** power) * ((1 - t) ** (power * (1 - peak) / peak))
    env /= env.max() + 1e-9
    fc = f0 * (f1 / f0) ** t
    s = lp_sweep(noise(n), fc) * env
    s = filt(s, lo=120)
    return s / (np.abs(s).max() + 1e-9)


def riser(dur, f0, f1, tone0=None, tone1=None):
    n = int(dur * SR)
    t = T(n) / dur
    s = lp_sweep(noise(n), f0 * (f1 / f0) ** t) * t ** 2.2
    s = s / (np.abs(s).max() + 1e-9)
    if tone0:
        tn = chirp(tone0, tone1, dur) * t ** 2.5
        s = s * 0.8 + tn * 0.35
    return s


def bell(f, dur=1.6, tau=0.55):
    n = int(dur * SR)
    t = T(n)
    s = np.zeros(n)
    for k, (r, a) in enumerate(zip((1, 2.76, 5.4, 8.93), (1, .5, .28, .12))):
        if f * r < SR / 2.2:
            s += a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / (tau / (1 + 0.5 * k)))
    s *= (1 - np.exp(-t / 0.002))
    return s


def pluck(f, dur=0.25, tau=0.09, cutoff=3500):
    n = int(dur * SR)
    t = T(n)
    s = saw(f, n, 8) * np.exp(-t / tau) * (1 - np.exp(-t / 0.002))
    return filt(s, hi=cutoff)


def blip(f, dur=0.04, g=1.0):
    n = int(dur * SR)
    t = T(n)
    return np.sin(2 * np.pi * f * t) * np.exp(-t / (dur / 3)) * g * (1 - np.exp(-t / 0.001))


def step():
    n = int(0.07 * SR)
    t = T(n)
    return np.sin(2 * np.pi * 85 * t) * np.exp(-t / 0.02) * 0.8 + \
        filt(noise(n), lo=1500) * np.exp(-t / 0.008) * 0.2


def keyclick():
    n = int(0.03 * SR)
    t = T(n)
    s = np.diff(noise(n) * np.exp(-t / 0.0025), prepend=0) * 0.5
    s += np.sin(2 * np.pi * (1700 + rng.random() * 700) * t) * np.exp(-t / 0.004) * 0.5
    return s


def crush(dur, k):
    n = int(dur * SR)
    t = T(n)
    s = np.repeat(noise(n // k + 1)[: n // k + 1], k)[:n]
    return np.sign(s) * np.minimum(np.abs(s), 1) * np.exp(-t / (dur / 3))


def duck(t):
    t = np.asarray(t)
    d = np.ones_like(t)
    m = (t >= 5.5) & (t < 10.0)
    d[m] = 1 - 0.55 * np.exp(-((t[m] - 5.5) % 0.5) / 0.1)
    return d


def pad(chord, t0, dur, g, cutoff, att, rel, rough=0.0):
    n = int(dur * SR)
    t = T(n)
    env = np.minimum(t / att, 1.0) * np.minimum(np.maximum(dur - t, 0) / rel, 1.0)
    env = env ** 1.5
    for side, dets in ((-0.55, (-0.004, 0.0)), (0.55, (0.0, 0.004))):
        s = np.zeros(n)
        for m in chord:
            for d in dets:
                f = mid(m) * (1 + d)
                for k in range(1, 7):
                    if f * k < SR / 2:
                        ph = 2 * np.pi * f * k * t
                        s += np.sin(ph + rough * np.sin(2 * np.pi * 5 * t)) / (k ** 1.2)
        s = filt(s * env, hi=cutoff)
        s *= duck(t0 + t)
        place(s, t0, g / (len(chord) ** 0.7), pan=side, send=0.35)


# ---------------------------------------------------------------- score
Am = [45, 57, 60, 64]
F = [41, 53, 57, 60]
C = [48, 55, 60, 64]
G = [43, 55, 59, 62]
Am9 = [45, 57, 60, 64, 71]
Fmaj7 = [41, 57, 60, 64]
DIS = [45, 51, 58, 63]
LOW = [33, 45, 52]

# ---- Beat 1 : minimalist prelude (0 - 2.5)
pad(Am, 0.0, 4.4, 0.16, 900, 2.0, 0.6)
for i in range(35):                                   # typing, steps(35) 0.25-1.05
    place(keyclick(), 0.25 + i * (0.8 / 35), g=0.10 + 0.07 * rng.random(), pan=-0.1)
place(whoosh(1.0, 400, 2500, 0.5), 0.7, g=0.05, pan=0.1)       # cursor glide
place(blip(2200, 0.06), 1.78, g=0.07, pan=0.4, send=0.3)        # hover tick
place(blip(1500, 0.03), 2.30, g=0.35, pan=0.4)                  # click down
place(blip(1100, 0.04), 2.38, g=0.22, pan=0.4)                  # click up
place(bell(mid(93), 1.2, 0.3), 2.32, g=0.05, pan=0.3, send=0.6)  # ripple shimmer

# ---- the turn : shatter (2.45 - 3.9)
place(whoosh(0.35, 800, 9000, 0.6), 2.40, g=0.45)
place(kick(120, 35, 0.9, 0.3), 2.45, g=0.95)
place(whoosh(0.5, 9000, 500, 0.15), 2.47, g=0.35, send=0.3)
for _ in range(70):                                   # glass
    t = 2.47 + rng.random() ** 1.8 * 1.2
    f = 2500 + rng.random() * 6500
    place(bell(f, 0.3, 0.06), t, g=0.05 + 0.04 * rng.random(), pan=rng.random() * 2 - 1, send=0.4)
scale = [76, 79, 81, 84, 88, 91, 93]                  # A-minor pentatonic-ish
for i in range(46):                                   # glyph cascade
    t = 2.7 + i * 0.026 + rng.random() * 0.02
    place(blip(mid(scale[int(rng.integers(0, len(scale)))] + 12 * int(rng.integers(0, 2))), 0.05),
          t, g=0.05 * (1 - i / 80), pan=rng.random() * 2 - 1, send=0.4)

# ---- Beat 2 : awakening (3 - 5.5)
place(riser(1.3, 200, 6000, 90, 700), 3.0, g=0.35, send=0.3)
for hb, gg in ((3.05, 0.35), (3.55, 0.5), (3.95, 0.65)):        # accelerating heartbeat
    place(kick(110, 40, 0.5, 0.12), hb, g=gg)
place(riser(0.35, 300, 5000), 3.95, g=0.3)
place(kick(100, 28, 1.6, 0.5), 4.30, g=1.25)                    # eye snaps open
place(filt(noise(int(1.6 * SR)), hi=6000) * np.exp(-T(int(1.6 * SR)) / 0.4), 4.30, g=0.35, send=0.4)
for j, f in enumerate((mid(57), mid(64), mid(69), mid(76))):    # ring chimes
    place(bell(f, 2.5, 1.0), 4.32 + j * 0.05, g=0.12, pan=-0.6 + 0.4 * j, send=0.6)
place(bell(mid(93), 1.5, 0.5), 4.65, g=0.10, send=0.6)          # pupil core ping
place(whoosh(0.75, 300, 9000, 0.45), 4.75, g=0.40, pan=0.2, send=0.2)   # leap
place(kick(140, 45, 0.5, 0.2), 5.55, g=0.8)                     # landing

# ---- Beat 3 : sprint & looting (5.5 - 10)
pad(F, 4.3, 3.9, 0.22, 2500, 0.05, 0.4)
pad(C, 8.2, 2.0, 0.22, 2500, 0.1, 0.4)
beats = np.arange(5.5, 10.0, 0.5)
for b in beats:
    place(kick(), b, g=0.95)
for t in np.arange(5.5, 10.0, 0.25):
    off = abs(((t - 5.5) / 0.5) % 1 - 0.5) < 1e-6
    place(hat(False), t, g=0.10 if off else 0.05, pan=0.3 if off else -0.2)
for t in (7.0, 8.0, 9.0):
    place(clap(), t, g=0.38, send=0.25)
for j in range(8):                                    # snare fill into the slop
    place(clap(), 9.5 + j * 0.0625, g=0.10 + 0.04 * j)
bpat = (1, 1, 2, 1, 1, 2, 1, 2)
for k, t in enumerate(np.arange(5.5, 10.0, 0.25)):
    root = 43.65 if t < 8.2 else 65.41
    f = root * bpat[k % 8]
    place(pluck(f, 0.24, 0.1, 700) + 0.7 * np.sin(2 * np.pi * root * T(int(0.24 * SR))) * np.exp(-T(int(0.24 * SR)) / 0.15),
          t, g=0.26)
ARP_F = (65, 69, 72, 69)
ARP_C = (67, 72, 76, 72)
for k, t in enumerate(np.arange(5.5, 10.0, 0.125)):
    note = (ARP_F if t < 8.2 else ARP_C)[k % 4]
    place(pluck(mid(note), 0.12, 0.06, 5000), t, g=0.05,
          pan=0.5 if k % 2 else -0.5, send=0.3)

tc = (6.85, 8.15, 9.35)
foot_groups = ((5.66, 6.5, 0.19), (7.15, 7.6, 0.15), (8.7, 8.85, 0.13), (9.8, 11.2, 0.12), (11.2, 13.45, 0.45))
for a, b_, iv in foot_groups:
    j = 0
    t = a
    while t < b_:
        place(step(), t, g=0.20, pan=-0.2 if j % 2 else 0.2)
        t += iv
        j += 1
place(whoosh(0.3, 500, 4000, 0.5), tc[0] - 0.45, g=0.25)         # vault
place(kick(120, 50, 0.3, 0.1), tc[0] + 0.3, g=0.3)
place(whoosh(0.7, 3000, 300, 0.4), tc[1] - 0.55, g=0.32, pan=0.2)  # slide
place(kick(120, 50, 0.3, 0.1), tc[1] + 0.35, g=0.3)
place(whoosh(0.8, 400, 5000, 0.4), tc[2] - 0.42, g=0.30, pan=-0.2)  # flip
place(kick(120, 50, 0.3, 0.1), tc[2] + 0.38, g=0.35)
for tcx, nt in zip(tc, (76, 81, 88)):                 # loot chimes (E5 A5 E6)
    place(bell(mid(nt), 1.8, 0.6), tcx, g=0.17, send=0.6)
    place(bell(mid(nt + 12), 1.4, 0.4), tcx + 0.04, g=0.08, pan=0.3, send=0.6)
    place(whoosh(0.35, 1500, 9000, 0.7), tcx - 0.1, g=0.16)       # orb absorb
    place(blip(mid(nt + 24), 0.06), tcx + 0.05, g=0.07, send=0.5)

# ---- Beat 4 : slop hazard (10 - 11.2) + Jev gate
pad(DIS, 10.0, 1.3, 0.20, 3000, 0.05, 0.1, rough=2.0)
for j in range(8):
    place(blip(311 if j % 2 else 466, 0.11, 1.0) * np.sign(np.sin(2 * np.pi * (311 if j % 2 else 466) * T(int(0.11 * SR)))),
          10.0 + j * 0.15, g=0.05, pan=-0.3 if j % 2 else 0.3)
for j, t in enumerate(np.arange(10.3, 11.25, 0.065)):    # glitch bars
    place(crush(0.025, int(rng.integers(2, 12))), t, g=0.05 + 0.006 * j, pan=rng.random() * 2 - 1)
place(riser(0.5, 300, 9000, 100, 1200), 10.7, g=0.30, send=0.3)

place(kick(120, 28, 1.4, 0.45), 11.2, g=1.3)             # time warp
place(np.sin(2 * np.pi * 35 * T(int(1.2 * SR))) * np.exp(-T(int(1.2 * SR)) / 0.55), 11.2, g=0.7)
place(chirp(1400, 60, 0.9) * np.exp(-T(int(0.9 * SR)) / 0.4), 11.2, g=0.16, send=0.5)
place(bell(mid(45), 3.0, 1.4), 11.2, g=0.16, send=0.7)
place(whoosh(0.5, 8000, 300, 0.2), 11.2, g=0.30, send=0.3)
pad(LOW, 11.2, 2.8, 0.30, 650, 0.3, 0.4)
j = 1
while 11.2 + 0.5 * j < 13.9:                           # half-time heartbeat
    place(kick(110, 38, 0.5, 0.14), 11.2 + 0.5 * j, g=0.50)
    place(blip(mid(88), 0.12), 11.45 + 0.5 * (j - 1), g=0.03, pan=0.5 if j % 2 else -0.5, send=0.7)
    j += 1
place_sweep(chirp(150, 4000, 1.0) * (0.5 + 0.5 * np.sin(2 * np.pi * 22 * T(int(1.0 * SR)))) ** 0.5,
            11.9, 0.14, -0.8, 0.8, send=0.3)             # emerald scan
place(whoosh(1.0, 400, 7000, 0.55), 11.9, g=0.22, send=0.3)
place(whoosh(0.35, 600, 3500, 0.5), 11.8, g=0.10, pan=0.6)       # HUD card in
for t in (11.9, 12.2, 12.55, 12.95):
    place(blip(2400, 0.03), t, g=0.05, pan=0.5)
for t, nt in zip((12.25, 12.62, 12.99), (84, 88, 93)):          # check dings
    place(bell(mid(nt), 1.2, 0.35), t, g=0.15, pan=0.4, send=0.5)
place(kick(100, 40, 0.5, 0.15), 13.25, g=0.6)                    # pad deploys
place(chirp(200, 900, 0.3) * np.exp(-T(int(0.3 * SR)) / 0.15), 13.25, g=0.10, send=0.3)
for i, nt in enumerate((72, 76, 81, 84, 88)):                    # chevrons
    place(blip(mid(nt), 0.08), 13.5 + i * 0.08, g=0.10, pan=-0.4 + 0.2 * i, send=0.4)
place(kick(120, 50, 0.3, 0.1), 13.5, g=0.25)
place(riser(0.45, 300, 8000, 200, 1800), 13.55, g=0.35, send=0.2)

# ---- launch (14.0 - 14.84)
pad(G, 13.9, 0.94, 0.22, 3500, 0.05, 0.05)
place(kick(200, 38, 1.0, 0.3), 14.0, g=1.35)
place(np.sin(2 * np.pi * 40 * T(int(0.9 * SR))) * np.exp(-T(int(0.9 * SR)) / 0.4), 14.0, g=0.7)
place(whoosh(0.8, 9000, 300, 0.12), 14.0, g=0.55, send=0.3)
place(bell(mid(57), 1.5, 0.8), 14.0, g=0.16, send=0.6)
place(chirp(120, 3500, 0.75) * np.linspace(0.3, 1, int(0.75 * SR)), 14.1, g=0.13, send=0.2)
place(whoosh(0.75, 400, 12000, 0.9, 3.0), 14.1, g=0.45, send=0.2)
for tk in (14.25, 14.5, 14.625, 14.75, 14.8):
    place(kick(150, 45, 0.3, 0.1), tk, g=0.8)
for j, t in enumerate(np.arange(14.1, 14.84, 0.0625)):
    place(hat(False), t, g=0.05 + 0.004 * j, pan=0.3 if j % 2 else -0.3)

# ---- Beat 5 : apex lock-up (15 - 20)
place(kick(160, 30, 1.8, 0.55), 15.0, g=1.3)
place(np.sin(2 * np.pi * 55 * T(int(2.2 * SR))) * np.exp(-T(int(2.2 * SR)) / 0.9), 15.0, g=0.65)
place(filt(noise(int(2.0 * SR)), lo=3500) * np.exp(-T(int(2.0 * SR)) / 0.7), 15.0, g=0.22, send=0.5)
for j, nt in enumerate((81, 84, 88, 93, 95)):
    place(bell(mid(nt), 2.6, 1.1), 15.0 + j * 0.06, g=0.11, pan=-0.6 + 0.3 * j, send=0.65)
pad(Am9, 15.0, 2.6, 0.26, 3500, 0.4, 1.0)
pad(Fmaj7, 17.4, 3.1, 0.22, 3000, 1.2, 1.6)
penta = (76, 79, 81, 84, 88, 91, 93, 96)
for j in range(10):                                     # crystal facets sparkle
    place(bell(mid(penta[j % 8]), 1.2, 0.35), 15.15 + j * 0.06, g=0.06, pan=-0.7 + 0.15 * j, send=0.6)
place(whoosh(0.9, 500, 7000, 0.5), 15.4, g=0.11, send=0.3)       # hairline
place(np.sin(2 * np.pi * 110 * T(int(1.0 * SR))) * np.exp(-T(int(1.0 * SR)) / 0.35), 15.55, g=0.34)  # title
place(bell(mid(69), 2.0, 0.8), 15.55, g=0.09, send=0.6)
place(chirp(1500, 6000, 0.9) * np.sin(np.pi * np.linspace(0, 1, int(0.9 * SR))), 16.0, g=0.035, send=0.6)  # shine
place(bell(mid(76), 1.6, 0.6), 16.2, g=0.08, send=0.6)           # subtitle
place(blip(mid(88), 0.07), 16.8, g=0.07, send=0.5)               # badge
place(blip(mid(93), 0.07), 16.88, g=0.06, send=0.5)
place(keyclick(), 17.2, g=0.10)                                   # terminal
note_cycle = (88, 84, 81, 76, 72, 76, 81, 84)
for j in range(9):                                       # sparse serene arpeggio
    place(bell(mid(note_cycle[j % 8]), 1.8, 0.7), 17.5 + j * 0.5, g=0.035 * (1 - j / 14), pan=0.4 if j % 2 else -0.4, send=0.7)

# ---------------------------------------------------------------- reverb
n_ir = int(2.2 * SR)
t_ir = T(n_ir)
wet_out = np.zeros_like(wet)
size = 1
while size < N + n_ir:
    size *= 2
for ch in (0, 1):
    ir = filt(noise(n_ir), hi=6000) * np.exp(-t_ir / 0.55)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
    ir /= np.sqrt(np.sum(ir ** 2))
    wet_out[ch] = np.fft.irfft(np.fft.rfft(wet[ch], size) * np.fft.rfft(ir, size), size)[:N]

mix = dry + wet_out * 0.55
mix = np.array([filt(mix[0], lo=24), filt(mix[1], lo=24)])

# ---------------------------------------------------------------- master gain shaping
tt = T(N)
gain = np.ones(N)
dip = (tt > 14.86) & (tt < 15.0)                         # inhale into the flash
gain[dip] = np.interp(tt[dip], [14.86, 14.88, 14.98, 15.0], [1.0, 0.06, 0.06, 1.0])
fade = tt >= 18.9
gain[fade] = np.interp(tt[fade], [18.9, 20.0], [1.0, 0.0])
mix = mix * gain
mix = mix[:, : int(DUR * SR)]

peak = np.abs(mix).max()
mix = np.tanh(mix / peak * 1.35) / np.tanh(1.35)
mix *= 0.93

os.makedirs(os.path.join(os.path.dirname(__file__), "..", "audio"), exist_ok=True)
out = os.path.join(os.path.dirname(__file__), "..", "audio", "soundtrack.wav")
pcm = (np.clip(mix.T, -1, 1) * 32767).astype("<i2")
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

print("wrote", os.path.abspath(out))
for s in range(20):
    seg = mix[:, s * SR:(s + 1) * SR]
    print("%2d-%2ds  rms %.3f  peak %.2f" % (s, s + 1, np.sqrt((seg ** 2).mean()), np.abs(seg).max()))
