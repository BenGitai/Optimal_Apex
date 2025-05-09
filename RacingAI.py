import pygame
import sys
import csv
import os
import math

pygame.font.init()
default_font = pygame.font.Font(None, 32)

# directory where your ‘assets’ folder lives (next to RacingAI.py)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')

# after loading asset_images, add:
sheet = pygame.image.load(os.path.join(ASSETS_DIR, 'road_tiles.png')).convert_alpha()
tile_w = sheet.get_width() // 3
tile_h = sheet.get_height() // 2

# indices: 0=no walls, 1=one wall, 2=opposite walls,
# 3=adjacent walls, 4=90° curve, 5=45° curve
road_tiles = [sheet.subsurface(pygame.Rect(col*tile_w, row*tile_h, tile_w, tile_h)).copy()
              for row in range(2) for col in range(3)]


def get_text_input(screen, prompt, font, box_rect, text_color=(255,255,255), box_color=(0,0,0), border_color=(255,255,255), border_width=2):
    """
    Pops up a text-entry box over `screen`, returns the entered string when Enter is pressed.
      • prompt: string to show before the user’s text
      • font: a pygame.Font
      • box_rect: pygame.Rect for the entry box
    """
    user_text = ""
    active = True
    clock = pygame.time.Clock()

    while active:
        for evt in pygame.event.get():
            if evt.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if evt.type == pygame.KEYDOWN:
                if evt.key == pygame.K_RETURN:
                    active = False
                elif evt.key == pygame.K_BACKSPACE:
                    user_text = user_text[:-1]
                else:
                    user_text += evt.unicode

        # draw translucent overlay
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0,0,0,180))
        screen.blit(overlay, (0,0))

        # draw box
        pygame.draw.rect(screen, box_color, box_rect)
        pygame.draw.rect(screen, border_color, box_rect, border_width)

        # render prompt + text
        txt_surf = font.render(f"{prompt}{user_text}", True, text_color)
        screen.blit(txt_surf, (box_rect.x + 5, box_rect.y + 5))

        pygame.display.update()
        clock.tick(30)

    return user_text


class Grid:
    def __init__(self, size, screen_size):
        self.size = size
        self.cell_size = screen_size // size
        self.grid = [[None for _ in range(size)] for _ in range(size)]

    def get_cell(self, x, y):
        grid_x = x // self.cell_size
        grid_y = y // self.cell_size
        return grid_x, grid_y

    def place_block(self, x, y, block):
        self.grid[y][x] = block

    def remove_block(self, x, y):
        self.grid[y][x] = None

    def get_block(self, x, y):
        return self.grid[y][x]

    def clear(self):
        self.grid = [[None for _ in range(self.size)] for _ in range(self.size)]

    def draw(self, screen):
        for y in range(self.size):
            for x in range(self.size):
                rect = pygame.Rect(x * self.cell_size, y * self.cell_size, self.cell_size, self.cell_size)
                pygame.draw.rect(screen, (200, 200, 200), rect, 1)
                if self.grid[y][x]:
                    pygame.draw.rect(screen, self.grid[y][x], rect)

class TrackEditor:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()
        self.grid_pixel_size = min(self.screen_width, self.screen_height) - 100  # Leave some space for UI
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
    
        self.grid_size = self.get_grid_size()
        self.init_grid()
    
        self.blocks = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
        ]
        self.selected_block = self.blocks[0]  # Start with the first block selected
        self.palette_rect = pygame.Rect(self.screen_width - 80, 0, 80, self.screen_height)

    def init_grid(self):
        self.grid = Grid(self.grid_size, self.grid_pixel_size)
        
    def get_grid_size(self):
        #size = int(input("Enter grid size (e.g., 20 for a 20x20 grid): "))
        box = pygame.Rect(self.screen.get_width()//2 - 150, self.screen.get_height()//2 - 20, 300, 40)
        size = get_text_input(self.screen, "Enter grid size (e.g., 20 for a 20x20 grid): ", default_font, box)
        size = int(size)
        if size < 1:
            size = 1
        return size

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "QUIT"
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_click(event.pos, event.button)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_s:
                        self.save_track()
                    elif event.key == pygame.K_l:
                        self.load_track()
                    elif event.key == pygame.K_ESCAPE:
                        return "MENU"

            self.screen.fill((200, 200, 200))  # Light gray background
            
            # Calculate the position to center the grid
            grid_x = (self.screen_width - self.grid_pixel_size) // 2
            grid_y = (self.screen_height - self.grid_pixel_size) // 2
            
            # Create a surface for the grid
            grid_surface = pygame.Surface((self.grid_pixel_size, self.grid_pixel_size))
            grid_surface.fill((0, 255, 0))  # Green background for the grid
            self.grid.draw(grid_surface)
            
            # Draw the grid surface on the main screen
            self.screen.blit(grid_surface, (grid_x, grid_y))
            
            self.draw_block_palette()
            self.draw_instructions()
            pygame.display.flip()
            self.clock.tick(60)

    def handle_click(self, pos, button):
        if self.palette_rect.collidepoint(pos):
            # Handle palette click
            self.handle_palette_click(pos)
        else:
            grid_x = (self.screen_width - self.grid_pixel_size) // 2
            grid_y = (self.screen_height - self.grid_pixel_size) // 2
            
            if grid_x <= pos[0] < grid_x + self.grid_pixel_size and grid_y <= pos[1] < grid_y + self.grid_pixel_size:
                cell_x, cell_y = self.grid.get_cell(pos[0] - grid_x, pos[1] - grid_y)
                if 0 <= cell_x < self.grid_size and 0 <= cell_y < self.grid_size:
                    if button == 1:  # Left click
                        if self.selected_block:
                            self.grid.place_block(cell_x, cell_y, self.selected_block)
                        else: # Remove block
                            self.grid.remove_block(cell_x, cell_y)
                    elif button == 3:  # Right click
                        self.grid.remove_block(cell_x, cell_y)

    def handle_palette_click(self, pos):
        index = (pos[1] - 20) // 40
        if 0 <= index < len(self.blocks):
            self.selected_block = self.blocks[index]
        elif index == len(self.blocks):
            self.selected_block = None  # Eraser

    def draw_block_palette(self):
        pygame.draw.rect(self.screen, (255, 255, 255), self.palette_rect)
        for i, color in enumerate(self.blocks):
            rect = pygame.Rect(self.screen_width - 60, 20 + i * 40, 40, 30)
            pygame.draw.rect(self.screen, color, rect)
            if color == self.selected_block:
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)
        rect = pygame.Rect(self.screen_width - 60, 20 + len(self.blocks) * 40, 40, 30)
        pygame.draw.rect(self.screen, (0, 0, 0), rect)  # Eraser
        if self.selected_block is None:
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 2)

    def draw_instructions(self):
        text = self.font.render("Left-click to place/remove blocks", True, (0, 0, 0))
        self.screen.blit(text, (10, 10))
        text = self.font.render("Right-click to remove blocks", True, (0, 0, 0))
        self.screen.blit(text, (10, 30))
        text = self.font.render("Press 'S' to save track", True, (0, 0, 0))
        self.screen.blit(text, (10, 50))
        text = self.font.render("Press 'L' to load track", True, (0, 0, 0))
        self.screen.blit(text, (10, 70))
        text = self.font.render("Press 'Esc' to return to menu", True, (0, 0, 0))
        self.screen.blit(text, (10, 90))

    def save_track(self):
        #file_name = input("Enter file name: ")
        box = pygame.Rect(self.screen.get_width()//2 - 150, self.screen.get_height()//2 - 20, 300, 40)
        file_name = get_text_input(self.screen, "Enter file name: ", default_font, box)
        with open(file_name + '.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            # Write the grid size as the first row
            writer.writerow([self.grid_size])
            for y in range(self.grid_size):
                for x in range(self.grid_size):
                    block = self.grid.get_block(x, y)
                    if block:
                        writer.writerow([x, y, block])

    def load_track(self):
        #file_name = input("Enter file name: ")
        box = pygame.Rect(self.screen.get_width()//2 - 150, self.screen.get_height()//2 - 20, 300, 40)
        file_name = get_text_input(self.screen, "Enter file name: ", default_font, box)
        if os.path.exists(file_name + '.csv'):
            with open(file_name + '.csv', 'r') as file:
                reader = csv.reader(file)
                # Read the grid size from the first row
                self.grid_size = int(next(reader)[0])
                # Reinitialize the grid with the new size
                self.init_grid()
                for row in reader:
                    x, y, block = row
                    self.grid.place_block(int(x), int(y), tuple(map(int, block[1:-1].split(','))))
            return self.grid  # Return the loaded grid
        else:
            print("File not found!")
            return None

class Car:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.angle = 0
        self.speed = 0
        self.max_speed = 5
        self.acceleration = 0.1
        self.deceleration = 0.05
        self.turn_speed = 3
        self.collision_detector = CarCollisionDetector(self)
        self.color = (255, 0, 0)  # Red car

        # physics parameters (tweak to taste)
        self.wheel_base = 50          # distance between axles in pixels
        self.max_steer = math.radians(30)  # max front‐wheel angle (±30°)
        self.steer_speed = math.radians(240)  # how fast you turn the wheels (rad/sec)
        self.mass = 1200             # mass in arbitrary units
        self.Cd = 0.425              # drag coefficient
        self.Crr = 12.8              # rolling resistance coeff

        # dynamic state
        self.velocity = 0.0          # forward speed (px/sec)
        self.yaw = math.radians(self.angle)  # vehicle heading (rad)
        self.steer = 0.0             # current front‐wheel steer angle (rad)

        # inputs
        self.throttle = 0.0          # in [0..1]
        self.brake_input = 0.0       # in [0..1]

        # maximum longitudinal forces (engine drives forward, brakes drive backward)
        self.max_engine_force = 500000.0    # adjust to taste
        self.max_brake_force  = -1000000.0   # negative so braking produces a backward force



    def accelerate(self):
        self.speed += self.acceleration
        if self.speed > self.max_speed:
            self.speed = self.max_speed

    def decelerate(self):
        self.speed -= self.acceleration
        if self.speed < -self.max_speed / 2:  # Slower in reverse
            self.speed = -self.max_speed / 2

    def brake(self):
        """Brakes (and if at 0, starts reversing)."""
        self.decelerate()

    def turn_left(self):
        if self.speed > 0:
            self.angle += self.turn_speed
        elif self.speed < 0:
            self.angle -= self.turn_speed
        # no turning when speed == 0

    def turn_right(self):
        if self.speed > 0:
            self.angle -= self.turn_speed
        elif self.speed < 0:
            self.angle += self.turn_speed
        # no turning when speed == 0

    def update(self, dt):
        # 1) Longitudinal forces
        # throttle produces forward force, brake_input produces backward force
        F_drive = self.throttle * self.max_engine_force  
        F_brake = self.brake_input * self.max_brake_force  
        # aerodynamic drag & rolling resistance
        F_drag = -self.Cd * self.velocity * abs(self.velocity)
        F_rr   = -self.Crr * self.velocity

        # net longitudinal acceleration
        a_long = (F_drive + F_brake + F_drag + F_rr) / self.mass
        # integrate velocity
        self.velocity += a_long * dt

        # 2) Update steering angle toward target
        # (you’ll set self.steer_target via input, see next section)
        steer_diff = self.steer_target - self.steer
        max_delta = self.steer_speed * dt
        # clamp how fast wheels turn
        steer_diff = max(-max_delta, min(steer_diff, max_delta))
        self.steer += steer_diff

        # 3) Kinematic bicycle motion
        if abs(self.steer) > 1e-4:
            turn_radius = self.wheel_base / math.tan(self.steer)
            angular_velocity = self.velocity / turn_radius
        else:
            angular_velocity = 0.0

        # integrate position & heading
        self.yaw -= angular_velocity * dt
        self.x += self.velocity * math.cos(self.yaw) * dt
        self.y += self.velocity * math.sin(self.yaw) * dt

        # keep your public-facing angle in degrees (for drawing)
        self.angle = -math.degrees(self.yaw)


    def draw(self, screen):
        # Create a surface for the car
        car_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(car_surface, self.color, (0, 0, self.width, self.height))
        
        # Rotate the car surface
        rotated_car = pygame.transform.rotate(car_surface, self.angle)
        
        # Get the rect of the rotated car and set its center
        rect = rotated_car.get_rect(center=(self.x, self.y))
        
        # Draw the rotated car on the screen
        screen.blit(rotated_car, rect.topleft)
        self.collision_detector.draw_debug(screen)

class Track:
    def __init__(self, name):
        self.name = name
        self.blocks = []
        self.grid_size = 0
        self.block_size = 0
        self.screen_size = 800  # We'll use a square screen
        self.load_track()

    def load_track(self):
        try:
            file_name = f"{self.name}.csv" if not self.name.endswith('.csv') else self.name
            full_path = os.path.abspath(file_name)
            print(f"Attempting to load track from: {full_path}")
            
            if not os.path.exists(full_path):
                print(f"File not found: {full_path}")
                return

            with open(full_path, 'r') as file:
                reader = csv.reader(file)
                # First row contains the grid size
                self.grid_size = int(next(reader)[0])
                self.block_size = self.screen_size // self.grid_size

                for row in reader:
                    if len(row) == 3:
                        x, y, color = int(row[0]), int(row[1]), eval(row[2])
                        # originally: self.blocks.append((x, y, color))
                        # now:
                        self.blocks.append((x, y, tile_index, rotation_angle))

            print(f"Successfully loaded track '{file_name}' with {len(self.blocks)} blocks")
            print(f"Grid size: {self.grid_size}, Block size: {self.block_size}")
        except FileNotFoundError:
            print(f"Track file '{file_name}' not found.")
        except Exception as e:
            print(f"Error loading track: {str(e)}")

    def draw(self, screen):
        # Fill the background with green
        screen.fill((0, 200, 0))  # Green color
        
        for x, y, idx, rot in self.blocks:
            img = road_tiles[idx]
            # rotate returns a new surface
            img_rot = pygame.transform.rotate(img, rot)
            rect = img_rot.get_rect(center=(
                x * self.block_size + self.block_size/2,
                y * self.block_size + self.block_size/2
            ))
            screen.blit(img_rot, rect.topleft)

        
        # Draw grid lines for debugging
        
        #for i in range(self.grid_size + 1):
         #   pygame.draw.line(screen, (0, 0, 0), (i * self.block_size, 0), (i * self.block_size, self.screen_size))
          #  pygame.draw.line(screen, (0, 0, 0), (0, i * self.block_size), (self.screen_size, i * self.block_size))
            

    def get_car_size(self):
        # Make the car size proportional to the grid
        car_width = self.block_size * 0.5  # 50% of a block width
        car_height = self.block_size * 0.25  # 25% of a block height
        return car_width, car_height

    def get_screen_size(self):
        return self.screen_size, self.screen_size

class CarCollisionDetector:
    def __init__(self, car):
        self.car = car
        self.listeners = [
            # corners
            ("top_left",      (-0.5, -0.5)),
            ("top_center",    ( 0.0, -0.5)),
            ("top_right",     ( 0.5, -0.5)),
            ("middle_left",   (-0.5,  0.0)),
            ("middle_right",  ( 0.5,  0.0)),
            ("bottom_left",   (-0.5,  0.5)),
            ("bottom_center", ( 0.0,  0.5)),
            ("bottom_right",  ( 0.5,  0.5)),
            # wheels (front left, front right, rear left, rear right)
            ("front_left_wheel",   (-0.4, -0.45)),
            ("front_right_wheel",  ( 0.4, -0.45)),
            ("rear_left_wheel",    (-0.4,  0.45)),
            ("rear_right_wheel",   ( 0.4,  0.45))
        ]
        self.last_colors = {name: None for name, _ in self.listeners}

    def get_listener_positions(self):
        import math
        rad   = -math.radians(self.car.angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        positions = []
        for name, (ox, oy) in self.listeners:
            # local offset in car-space
            dx = ox * self.car.width
            dy = oy * self.car.height
            # rotate by car.angle
            rx = dx * cos_a - dy * sin_a
            ry = dx * sin_a + dy * cos_a
            # translate into screen-space
            x = int(self.car.x + rx)
            y = int(self.car.y + ry)
            positions.append((name, x, y))

        return positions


    def update_colors(self, colors):
        for name, color in colors.items():
            if color != self.last_colors[name]:
                print(f"Listener '{name}' detected new color: {color}")
                self.last_colors[name] = color
    def update(self, colors):
        for name, color in colors.items():
            if color != self.last_colors[name]:
                print(f"Listener '{name}' detected new color: {color}")
                self.last_colors[name] = color

    def draw_debug(self, screen):
        for _, x, y in self.get_listener_positions():
            pygame.draw.circle(screen, (255, 0, 0), (x, y), 2)

class Menu:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.Font(None, 36)
        self.options = ["Track Editor", "Car Editor", "Load Game", "Quit"]
        self.selected = 0

    def draw(self):
        self.screen.fill((255, 255, 255))
        for i, option in enumerate(self.options):
            color = (255, 0, 0) if i == self.selected else (0, 0, 0)
            text = self.font.render(option, True, color)
            self.screen.blit(text, (100, 100 + i * 50))
        pygame.display.flip()

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_RETURN:
                return self.options[self.selected]
        return None

def drive_car(screen, track_name):
    track = Track(track_name)
    if not track.blocks:  # If no blocks were loaded, return to menu
        print("Failed to load track. Returning to menu.")
        return "MENU"

    screen_size = track.get_screen_size()
    screen = pygame.display.set_mode(screen_size)  # Resize the screen
    
    car_width, car_height = track.get_car_size()
    
    # Place the car at the center of the screen
    car_x = (screen_size[0] - car_width) / 2
    car_y = (screen_size[1] - car_height) / 2
    
    car = Car(car_x, car_y, car_width, car_height)
    
    clock = pygame.time.Clock()
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "MENU"
        
        # compute dt (in seconds)
        dt = clock.tick(60) / 1000.0

        keys = pygame.key.get_pressed()
        # throttle & brake as normalized inputs
        car.throttle     = 1.0 if keys[pygame.K_UP] else 0.0
        car.brake_input  = 1.0 if (keys[pygame.K_DOWN] and (car.velocity > 0)) else 0.0
        if car.velocity < 0:
            car.velocity = 0.0  # stop reversing if brake pressed

        # steering target: left/right arrow sets desired wheel angle
        if keys[pygame.K_LEFT]:
            car.steer_target =  car.max_steer
        elif keys[pygame.K_RIGHT]:
            car.steer_target = -car.max_steer
        else:
            car.steer_target = 0.0

        # update with real physics
        car.update(dt)
        
        screen.fill((0, 200, 0))  # Fill the background with green
        track.draw(screen)  # Draw the track
        
        # Get collision detector positions
        listener_positions = car.collision_detector.get_listener_positions()
        
        # Check colors at listener positions
        colors = {}
        for name, x, y in listener_positions:
            # Ensure the coordinates are within the screen bounds
            x = max(0, min(int(x), screen.get_width() - 1))
            y = max(0, min(int(y), screen.get_height() - 1))
            colors[name] = screen.get_at((x, y))
        
        # Update collision detector with new colors
        car.collision_detector.update_colors(colors)  # Changed from update to update_colors
        
        car.draw(screen)  # Draw the car
        
        pygame.display.flip()
        clock.tick(60)

def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 800))  # Start with a square screen
    pygame.display.set_caption("Racing Game")
    clock = pygame.time.Clock()

    print(f"Current working directory: {os.getcwd()}")

    menu = Menu(screen)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            else:
                option = menu.handle_input(event)
                if option:
                    if option == "Track Editor":
                        track_editor = TrackEditor(screen)
                        result = track_editor.run()
                        if result == "QUIT":
                            pygame.quit()
                            sys.exit()
                        elif result == "MENU":
                            menu = Menu(screen)
                    elif option == "Car Editor":
                        # Implement car editor
                        pass
                    elif option == "Load Game":
                        #track_name = input("Enter track name to load: ")
                        box = pygame.Rect(screen.get_width()//2 - 150, screen.get_height()//2 - 20, 300, 40)
                        track_name = get_text_input(screen, "Enter track name to load: ", default_font, box)
                        result = drive_car(screen, track_name)
                        if result == "QUIT":
                            pygame.quit()
                            sys.exit()
                        elif result == "MENU":
                            # Reinitialize the menu with the original screen size
                            screen = pygame.display.set_mode((800, 800))
                            menu = Menu(screen)
                    elif option == "Quit":
                        pygame.quit()
                        sys.exit()

        menu.draw()
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()

