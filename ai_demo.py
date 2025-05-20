import pygame, sys, os
import RacingAI
from RacingAI import Track, Car

class DemoAI:
    """A trivial AI: always full-throttle straight ahead."""
    def get_actions(self, car, keys, dt):
        return 1.0, 0.0, 0.0  # throttle, brake_input, steer_target

def main(track_name="test"):
    # 1) Initialize Pygame & font
    pygame.init()
    pygame.font.init()
    default_font = pygame.font.Font(None, 32)

    # 2) Load track and open the window
    track = Track(track_name)
    screen = pygame.display.set_mode(track.get_screen_size())
    pygame.display.set_caption("AI Demo")

    # 3) Convert & slice assets after display init
    if RacingAI.road_tiles is None:
        raw_sheet = pygame.image.load(
            os.path.join(RacingAI.ASSETS_DIR, 'TrackPieces.png')
        )
        sheet = raw_sheet.convert_alpha()
        tw = sheet.get_width()  // 3
        th = sheet.get_height() // 3
        RacingAI.road_tiles = [
            sheet.subsurface(pygame.Rect(col*tw, row*th, tw, th)).copy()
            for row in range(3) for col in range(3)
        ]
    if RacingAI.CAR_IMAGE_RAW is None:
        raw_car = pygame.image.load(
            os.path.join(RacingAI.ASSETS_DIR, 'CarSprite.png')
        )
        RacingAI.CAR_IMAGE_RAW = raw_car.convert_alpha()

    # 4) Spawn the car at the start
    car_w, car_h = track.get_car_size()
    gx, gy = track.spawn_point or (0, 0)
    x = gx*track.block_size + track.block_size/2 - car_w/2
    y = gy*track.block_size + track.block_size/2 - car_h/2
    car = Car(x, y, car_w, car_h)

    # 5) Create the AI controller
    ai = DemoAI()

    # 6) Prepare off-screen surface for drawing & collision sampling
    track_surface = pygame.Surface(screen.get_size())

    clock = pygame.time.Clock()
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

        # 1) Build the map into an off-screen surface
        track_surface.fill((0,200,0))         # grass background
        track.draw(track_surface)             # road tiles

        # 2) Draw the finish line
        bs = track.block_size
        if getattr(track, 'finish_line', None) and len(track.finish_line) == 2:
            (x1,y1),(x2,y2) = track.finish_line
            p1 = (x1*bs + bs//2, y1*bs + bs//2)
            p2 = (x2*bs + bs//2, y2*bs + bs//2)
            pygame.draw.line(track_surface, (255,255,255), p1, p2, max(1, bs//10))

        # 3) Draw the checkpoint segments
        for (cx1,cy1),(cx2,cy2) in getattr(track, 'checkpoint_lines', []):
            q1 = (cx1*bs + bs//2, cy1*bs + bs//2)
            q2 = (cx2*bs + bs//2, cy2*bs + bs//2)
            pygame.draw.line(track_surface, (255,165,0), q1, q2, max(1, bs//10))

        # 4) Draw the checkpoint numbers
        for idx, ((cx1,cy1),(cx2,cy2)) in enumerate(getattr(track, 'checkpoint_lines', [])):
            # midpoint in pixels
            mx = (cx1*bs + cx2*bs + bs) // 2
            my = (cy1*bs + cy2*bs + bs) // 2
            lbl = default_font.render(str(idx+1), True, (0,0,0))
            rect = lbl.get_rect(center=(mx,my))
            track_surface.blit(lbl, rect)

        # 5) Tell the AI to act & advance the car
        thr, brk, steer = ai.get_actions(car, None, dt)
        car.throttle    = thr
        car.brake_input = brk
        car.steer_target= steer
        car.update(dt)

        # 6) Sample collisions exactly as in player mode
        colors = {}
        for name, xp, yp in car.collision_detector.get_listener_positions():
            xp = max(0, min(xp, track_surface.get_width()-1))
            yp = max(0, min(yp, track_surface.get_height()-1))
            colors[name] = track_surface.get_at((xp, yp))
        car.collision_detector.update_colors(colors)
        if car.collision_detector.check_wall_collision(colors):
            car.handle_collision()
        elif car.collision_detector.any_wheel_offtrack(colors):
            car.Crr = car.Crr_sand
        else:
            car.Crr = car.Crr_normal

        # 7) Finally blit everything and draw the car
        screen.blit(track_surface, (0,0))
        car.draw(screen)
        pygame.display.flip()

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main("test")  # replace "test" with your track filename (without .csv)
