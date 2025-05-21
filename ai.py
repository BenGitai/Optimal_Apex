# ai.py

import random, math, pygame, os
from RacingAI import Track, Car, RaceManager, ASSETS_DIR
import json

# ─── Genome & Neural Net ──────────────────────────────────────────────────

class Genome:
    """A flat list of weights."""
    def __init__(self, length):
        self.weights = [random.uniform(-1,1) for _ in range(length)]

    def mutate(self, rate=0.1, scale=0.5):
        for i in range(len(self.weights)):
            if random.random() < rate:
                self.weights[i] += random.uniform(-scale, scale)

    def save(self, path):
        """Serialize this genome’s weight list to a JSON file."""
        with open(path, 'w') as f:
            json.dump(self.weights, f)

    @classmethod
    def load(cls, path):
        """
        Load a genome from a JSON file previously written by `save`.
        Returns a new Genome with its `.weights` set to the file’s data.
        """
        with open(path, 'r') as f:
            weights = json.load(f)
        g = cls(len(weights))
        g.weights = weights
        return g

    @staticmethod
    def crossover(a, b):
        assert len(a.weights) == len(b.weights)
        p = random.randrange(1, len(a.weights))
        child = Genome(len(a.weights))
        child.weights = a.weights[:p] + b.weights[p:]
        return child

class NeuralNet:
    """Single‐layer tanh net: inputs→outputs."""
    def __init__(self, genome, n_in, n_out):
        self.g = genome
        self.n_in  = n_in
        self.n_out = n_out

    def activate(self, inputs):
        outs = []
        for j in range(self.n_out):
            s = 0.0
            for i in range(self.n_in):
                s += self.g.weights[j*self.n_in + i] * inputs[i]
            outs.append(math.tanh(s))
        return outs

# ─── AI Controller ────────────────────────────────────────────────────────

class AIController:
    """
    Wraps a NeuralNet and your game’s sensors to produce throttle, brake, steer.
    """
    def __init__(self, genome, track, manager):
        self.net     = NeuralNet(genome, 7 + 1 + 2 + 1, 3)
        self.track   = track
        self.manager = manager
        # will be set each frame to the off-screen map
        self.track_surface = None

    def get_actions(self, car, dt):
        # 1) LIDAR
        lidar = car.get_lidar(
            self.track_surface,
            num_rays=7,
            fov=math.pi * 0.75,
            max_dist=car.width * 10,
            step=4
        )
        # 2) speed
        speed = car.velocity
        # 3) next‐checkpoint info
        dist, angle = self.manager.get_next_checkpoint_info(car)
        # 4) current steering
        steer_curr = car.steer

        # build input vector
        inputs = lidar + [speed, dist, angle, steer_curr]
        raw_outputs = self.net.activate(inputs)

        # map outputs to controls
        thr = max(0.0, raw_outputs[0])
        brk = max(0.0, -raw_outputs[1])
        steer = raw_outputs[2] * car.max_steer
        return thr, brk, steer

# ─── Evaluation ───────────────────────────────────────────────────────────

def evaluate(genome, track_name,
             sim_time=20.0, fps=60, render=False):
    """
    Runs one car with the given genome on track_name.
    If render=True, opens a window and animates it.
    Returns fitness = laps*1000 − lap_time.
    """
    # lazy‐init slicing of road_tiles & car sprite, exactly as ai_demo does
    import RacingAI

    # ─── Ensure road_tiles is populated ───
    if RacingAI.road_tiles is None:
        raw = pygame.image.load(os.path.join(RacingAI.ASSETS_DIR, 'TrackPieces.png'))
        sheet = raw.convert_alpha() if render else raw
        tw = sheet.get_width()  // 3
        th = sheet.get_height() // 3
        RacingAI.road_tiles = [
            sheet.subsurface(pygame.Rect(col*tw, row*th, tw, th)).copy()
            for row in range(3) for col in range(3)
        ]

    # ─── Ensure CAR_IMAGE_RAW is populated for render ───
    if render and RacingAI.CAR_IMAGE_RAW is None:
        raw_car = pygame.image.load(os.path.join(RacingAI.ASSETS_DIR, 'CarSprite.png'))
        RacingAI.CAR_IMAGE_RAW = raw_car.convert_alpha()

    if render and CAR_IMAGE_RAW is None:
        raw_car = pygame.image.load(
            os.path.join(ASSETS_DIR, 'CarSprite.png')
        )
        from RacingAI import CAR_IMAGE_RAW as _car
        _car[:] = raw_car.convert_alpha()

    # load track & spawn
    pygame.font.init()
    track = Track(track_name)
    sx, sy = track.get_screen_size()
    surf = pygame.Surface((sx, sy))

    cw, ch = track.get_car_size()
    gx, gy = track.spawn_point or (0,0)
    x = gx*track.block_size + track.block_size/2 - cw/2
    y = gy*track.block_size + track.block_size/2 - ch/2
    car = Car(x, y, cw, ch)

    mgr = RaceManager(track, pygame.font.Font(None,1))
    ctrl = AIController(genome, track, mgr)

    # if rendering, open window
    if render:
        pygame.init()
        pygame.font.init()
        screen = pygame.display.set_mode((sx, sy))
        pygame.display.set_caption("AI Training Demo")

    clock     = pygame.time.Clock()
    max_frames = int(sim_time * fps)

    for _ in range(max_frames):
        # redraw map
        surf.fill((0,200,0))
        track.draw(surf)
        # finish & checkpoints
        bs = track.block_size
        if len(track.finish_line)==2:
            (x1,y1),(x2,y2)=track.finish_line
            pygame.draw.line(
                surf, (255,255,255),
                (x1*bs+bs//2, y1*bs+bs//2),
                (x2*bs+bs//2, y2*bs+bs//2),
                max(1, bs//10)
            )
        for (cx1,cy1),(cx2,cy2) in getattr(track,'checkpoint_lines',[]):
            pygame.draw.line(
                surf, (255,165,0),
                (cx1*bs+bs//2, cy1*bs+bs//2),
                (cx2*bs+bs//2, cy2*bs+bs//2),
                max(1, bs//10)
            )

        # AI senses & acts
        ctrl.track_surface = surf
        dt = clock.tick(fps) / 1000.0
        thr, brk, steer = ctrl.get_actions(car, dt)
        car.throttle, car.brake_input, car.steer_target = thr, brk, steer

        # physics & collisions
        car.update(dt)
        cols = {}
        for name, xp, yp in car.collision_detector.get_listener_positions():
            xp = max(0, min(xp, sx-1))
            yp = max(0, min(yp, sy-1))
            cols[name] = surf.get_at((xp, yp))
        car.collision_detector.update_colors(cols)
        if car.collision_detector.check_wall_collision(cols):
            car.handle_collision()
        elif car.collision_detector.any_wheel_offtrack(cols):
            car.Crr = car.Crr_sand
        else:
            car.Crr = car.Crr_normal

        mgr.update(car)

        if render:
            screen.blit(surf, (0,0))
            car.draw(screen)
            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    render = False

        if mgr.lap_count >= 1:
            break

    total_t = sum(mgr.lap_times) if mgr.lap_times else sim_time
    return mgr.lap_count * 1000.0 - total_t

class GA:
    """
    A simple genetic algorithm over Genome instances.
    """
    def __init__(self, pop_size, genome_length):
        # initialize a population of random genomes
        self.population = [Genome(genome_length) for _ in range(pop_size)]

    def evolve(self, scored, retain=0.2, random_select=0.05, mutate_rate=0.1):
        """
        scored: list of (genome, fitness) tuples
        retain: fraction of top performers to keep
        random_select: chance to keep some lower performers
        mutate_rate: mutation probability per weight
        """
        # 1) grade by fitness descending
        graded = sorted(scored, key=lambda x: x[1], reverse=True)
        # 2) retain the top fraction
        retain_length = int(len(graded) * retain)
        parents = [g for g,_ in graded[:retain_length]]
        # 3) randomly keep some weaker ones for diversity
        for g,_ in graded[retain_length:]:
            if random.random() < random_select:
                parents.append(g)
        # 4) crossover + mutate to fill up to original pop size
        desired = len(self.population) - len(parents)
        children = []
        while len(children) < desired:
            dad, mum = random.sample(parents, 2)
            child = Genome.crossover(dad, mum)
            child.mutate(rate=mutate_rate)
            children.append(child)
        # 5) new generation
        self.population = parents + children