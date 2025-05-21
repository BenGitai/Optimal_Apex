import pygame, sys, os, math, random
from RacingAI import Track, Car, compute_spawns, ASSETS_DIR
from RacingAI import default_font as _unused  # ensure font code is present
from RacingAI import RaceManager
import RacingAI
import numpy as np

import neat
from neat.nn import FeedForwardNetwork

def main_visual_ga(track_name="test",
                   pop_size=20,
                   generation_time=30.0,
                   fps=60):
    pygame.init()
    pygame.font.init()
    font = pygame.font.Font(None, 24)

    # load track + window
    track = Track(track_name)
    sx, sy = track.get_screen_size()
    screen = pygame.display.set_mode((sx, sy))
    pygame.display.set_caption("Live GA Training")
    clock = pygame.time.Clock()

    # prepare tiles & car sprite (same as ai_demo)
    from RacingAI import road_tiles, CAR_IMAGE_RAW
    if road_tiles is None:
        raw = pygame.image.load(os.path.join(ASSETS_DIR, 'TrackPieces.png'))
        sheet = raw.convert_alpha()
        tw, th = sheet.get_width()//3, sheet.get_height()//3
        RacingAI.road_tiles = [
            sheet.subsurface(pygame.Rect(c*tw, r*th, tw, th)).copy()
            for r in range(3) for c in range(3)
        ]
    if CAR_IMAGE_RAW is None:
        raw_car = pygame.image.load(os.path.join(ASSETS_DIR, 'CarSprite.png'))
        RacingAI.CAR_IMAGE_RAW = raw_car.convert_alpha()

    # init NEAT
    cfg_path = os.path.join(os.path.dirname(__file__),
                            'config-feedforward.ini')
    config   = neat.Config(neat.DefaultGenome,
                           neat.DefaultReproduction,
                           neat.DefaultSpeciesSet,
                           neat.DefaultStagnation,
                           cfg_path)
    pop = neat.Population(config)
    pop.add_reporter(neat.StdOutReporter(True))
    pop.add_reporter(neat.StatisticsReporter())


    generation = 0
    while True:
        generation += 1
        print(f"Generation {generation}")
        # spawn one Car+Controller+Manager for each genome
        cars        = []
        controllers = []
        managers    = []
        spawns = compute_spawns(track.spawn_point, pop_size, False, track)

        # pull genomes out of pop.population (dict of {id:genome})
        genome_list = list(pop.population.values())

        for idx, genome in enumerate(genome_list):
            x,y = spawns[idx]
            cw,ch = track.get_car_size()
            car = Car(x, y, cw, ch)
            cars.append(car)
            mgr = RaceManager(track, font)
            managers.append(mgr)

            net = FeedForwardNetwork.create(genome, config)
            controllers.append(net)

        # — initialize shaped‐reward bookkeeping —
        crash_penalty     = 50.0
        idle_penalty_rate = 10.0     # per second idling
        proximity_scale   = 200.0    # per‐pixel reduction → reward
        max_idle_speed    = 0.1      # below this, we call “idle”
        lap_bonus         = 1000.0
        HEADING_SCALE    = 100.0    # tune this
        SPEED_SCALE      = 20.0
        WALL_THRESH      = track.block_size * 0.3
        WALL_SCALE       = 200.0
        CHECKPOINT_BONUS = 200.0
        STEER_PENALTY = 5.0   # per radian per second
        STRAIGHT_BONUS = 10


        fitness_scores = [0.0] * len(genome_list)
        prev_dists     = []
        # record initial distance to next checkpoint for each car
        for car, mgr in zip(cars, managers):
            d, _ = mgr.get_next_checkpoint_info(car)
            prev_dists.append(d)

        # — extra bookkeeping —
        last_cp_idxs = [mgr.current_cp_idx for mgr in managers]
        last_positions = [(car.x, car.y) for car in cars]


        start_ticks = pygame.time.get_ticks()
        # run one generation
        while (pygame.time.get_ticks() - start_ticks)/1000.0 < generation_time:
            dt = clock.tick(fps) / 1000.0
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            # redraw track + lines into an offscreen surface
            track_surf = pygame.Surface((sx, sy))
            track_surf.fill((0,200,0))
            track.draw(track_surf)
            bs = track.block_size
            if len(track.finish_line)==2:
                (x1,y1),(x2,y2)=track.finish_line
                p1=(x1*bs+bs//2,y1*bs+bs//2)
                p2=(x2*bs+bs//2,y2*bs+bs//2)
                pygame.draw.line(track_surf,(255,255,255),p1,p2,max(1,bs//10))
            for (cx1,cy1),(cx2,cy2) in getattr(track,'checkpoint_lines',[]):
                q1=(cx1*bs+bs//2,cy1*bs+bs//2)
                q2=(cx2*bs+bs//2,cy2*bs+bs//2)
                pygame.draw.line(track_surf,(255,165,0),q1,q2,max(1,bs//10))

            # update each car
            for idx, (car, ctrl, mgr) in enumerate(zip(cars, controllers, managers)):
                # sense & act
                ctrl.track_surface = track_surf

                # `ctrl` is now a FeedForwardNetwork
                # build the NN inputs exactly as before:
                rays = car.get_lidar(track_surf, num_rays=7,
                                     fov=math.pi*0.75,
                                     max_dist=car.width*10, step=4)
                dist, ang = mgr.get_next_checkpoint_info(car)
                inputs = rays + [car.velocity, dist, ang, car.steer]
                out    = ctrl.activate(inputs)

                thr   = max(0.0, out[0])
                brk   = max(0.0, -out[1])

                # dead‐zone steering
                raw_s = out[2]
                DEAD_ZONE = 0.1    # tune between 0.0 and 1.0
                if (-DEAD_ZONE < abs(raw_s) < DEAD_ZONE):
                    steer = 0.0
                else:
                    # re‐scale so you still can hit full lock
                    steer = (raw_s - math.copysign(DEAD_ZONE, raw_s)) / (1.0 - DEAD_ZONE)
                steer = steer * car.max_steer


                car.throttle, car.brake_input, car.steer_target = thr, brk, steer
                car.update(dt)
                # collision sampling
                cols = {}
                for name, xp, yp in car.collision_detector.get_listener_positions():
                    xp = max(0, min(xp, sx-1))
                    yp = max(0, min(yp, sy-1))
                    cols[name] = track_surf.get_at((xp, yp))
                car.collision_detector.update_colors(cols)
                if car.collision_detector.check_wall_collision(cols):
                    car.handle_collision()
                elif car.collision_detector.any_wheel_offtrack(cols):
                    car.Crr = car.Crr_sand
                else:
                    car.Crr = car.Crr_normal
                mgr.update(car)

                # compute fitness

                # 1) proximity reward
                new_dist, _ = mgr.get_next_checkpoint_info(car)
                delta = prev_dists[idx] - new_dist
                fitness_scores[idx] += delta * proximity_scale
                prev_dists[idx] = new_dist

                # 2) idle penalty
                if abs(car.velocity) < max_idle_speed:
                    fitness_scores[idx] -= idle_penalty_rate * dt

                # 3) lap bonus
                if mgr.lap_count >= 1:
                    fitness_scores[idx] += lap_bonus

                # 4) crash penalty (if it jumped over from earlier)
                if car.collision_detector.check_wall_collision(cols):
                    fitness_scores[idx] -= crash_penalty


                # 5) heading‐alignment bonus
                import numpy as np
                # get unit heading vector
                heading_vec = np.array([math.cos(car.yaw), math.sin(car.yaw)])
                # get vector along the track between current and next CP
                cp_idx = mgr.current_cp_idx
                cp1, cp2 = track.checkpoint_lines[cp_idx]
                p1 = np.array([cp1[0]*bs + bs/2, cp1[1]*bs + bs/2])
                p2 = np.array([cp2[0]*bs + bs/2, cp2[1]*bs + bs/2])
                tangent = (p2 - p1)
                tangent = tangent / np.linalg.norm(tangent)
                dot = float(np.dot(heading_vec, tangent))
                fitness_scores[idx] += max(dot, 0) * HEADING_SCALE

                # 6) forward‐speed bonus
                fitness_scores[idx] += max(car.velocity, 0) * SPEED_SCALE

                # 7) wall‐proximity penalty via LIDAR
                dists = car.get_lidar(
                    track_surf, num_rays=7,
                    fov=math.pi*0.75,
                    max_dist=car.width*10, step=4
                )
                min_d = min(dists)
                if min_d < WALL_THRESH:
                    fitness_scores[idx] -= (WALL_THRESH - min_d) * WALL_SCALE

                # 8) small bonus the moment you cross a checkpoint
                if mgr.current_cp_idx > last_cp_idxs[idx]:
                    fitness_scores[idx] += CHECKPOINT_BONUS
                    last_cp_idxs[idx] = mgr.current_cp_idx
                
                # 9) steering penalty
                fitness_scores[idx] -= abs(car.steer_target) * STEER_PENALTY * dt
                fitness_scores[idx] += (1.0 - abs(steer)) * STRAIGHT_BONUS * dt

                # update last_positions if you need them elsewhere
                last_positions[idx] = (car.x, car.y)

                

            # draw everything
            screen.blit(track_surf, (0,0))
            for idx, car in enumerate(cars):
                car.draw(screen)
            # HUD: gen + timer
            elapsed = (pygame.time.get_ticks() - start_ticks)/1000.0
            txt = font.render(
                f"Gen {generation}  Time {elapsed:.1f}/{generation_time}s", True, (0,0,0)
            )
            screen.blit(txt, (10,10))
            pygame.display.flip()

        # assign fitness back onto each genome
        for i, (genome, mgr) in enumerate(zip(genome_list, managers)):
            # combine shaped reward with any lap bonus already counted
            genome.fitness = fitness_scores[i]
            print(f"Genome {i} fitness: {genome.fitness:.1f}")

        # now tell NEAT to produce the next generation
        new_pop = pop.reproduction.reproduce(
            config, pop.species, pop_size, generation
        )
        pop.population = new_pop
        pop.species.speciate(config, pop.population, generation)
        pop.generation += 1


if __name__ == "__main__":
    main_visual_ga("test", pop_size=30, generation_time=5, fps=60)
