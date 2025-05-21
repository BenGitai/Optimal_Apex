import pygame, sys, os, math, random
from RacingAI import Track, Car, compute_spawns, ASSETS_DIR
from RacingAI import default_font as _unused  # ensure font code is present
from ai import Genome, NeuralNet, GA, AIController
from RacingAI import RaceManager
import RacingAI

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

    # init GA
    genome_length = (7 + 1 + 2 + 1) * 3
    ga = GA(pop_size, genome_length)

    generation = 0
    while True:
        generation += 1
        # spawn one Car+Controller+Manager for each genome
        cars        = []
        controllers = []
        managers    = []
        spawns = compute_spawns(track.spawn_point, pop_size, False, track)
        for idx, genome in enumerate(ga.population):
            x,y = spawns[idx]
            cw,ch = track.get_car_size()
            car = Car(x, y, cw, ch)
            cars.append(car)
            mgr = RaceManager(track, font)
            managers.append(mgr)
            ctrl = AIController(genome, track, mgr)
            controllers.append(ctrl)

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
            for car, ctrl, mgr in zip(cars, controllers, managers):
                # sense & act
                ctrl.track_surface = track_surf
                thr, brk, steer = ctrl.get_actions(car, dt)
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

        # end of generation: score & evolve
        scored = []
        for genome, mgr in zip(ga.population, managers):
            lap_t = sum(mgr.lap_times) if mgr.lap_times else generation_time
            fitness = mgr.lap_count*1000.0 - lap_t
            scored.append((genome, fitness))
            print(f"Genome {genome} scored {fitness:.1f}ms")
        ga.evolve(scored)

if __name__ == "__main__":
    main_visual_ga("test", pop_size=30, generation_time=10.0, fps=60)
