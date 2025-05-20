import pygame
import sys
import csv
import os
import math

pygame.font.init()
default_font = pygame.font.Font(None, 32)

pygame.init()
screen = pygame.display.set_mode((800, 800))

# directory where your ‘assets’ folder lives (next to RacingAI.py)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
_sheet_raw = pygame.image.load(os.path.join(ASSETS_DIR, 'TrackPieces.png'))
sheet   = _sheet_raw.convert_alpha()
tile_w  = sheet.get_width()  // 3
tile_h  = sheet.get_height() // 3

# this road_tiles list is now global to the module
road_tiles = [
    sheet.subsurface(pygame.Rect(col*tile_w, row*tile_h, tile_w, tile_h)).copy()
    for row in range(3) for col in range(3)
]

CAR_IMAGE_RAW = pygame.image.load(os.path.join(ASSETS_DIR, 'CarSprite.png')).convert_alpha()

# Terrain‐sensor colors
GRASS_COLOR    = (  0,200,  0)   # off‐road grass
SAND_COLOR     = (255,255,  0)   # yellow = sand
GRAVEL_COLOR   = (  0,  0,  0)   # black = gravel
CURB_BLUE_COLOR= (  0,  0,255)   # blue = slight curb

# Friction multipliers relative to your normal rolling‐resistance
Crr_NORMAL_MULT = 1.0
Crr_BLUE_MULT   = 1.5
Crr_GRASS_MULT  = 3.0
Crr_GRAVEL_MULT = 5.0
Crr_SAND_MULT   = 8.0

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

    def place_block(self, x, y, block, rotation=0):
        """
        x, y       — cell coordinates
        block      — a pygame.Surface
        rotation   — degrees to rotate that surface
        """
        self.grid[y][x] = (block, rotation)

    def remove_block(self, x, y):
        self.grid[y][x] = None

    def get_block(self, x, y):
        return self.grid[y][x]

    def clear(self):
        self.grid = [[None for _ in range(self.size)] for _ in range(self.size)]

    def draw(self, screen):
        for y in range(self.size):
            for x in range(self.size):
                # cell border
                rect = pygame.Rect(
                    x * self.cell_size,
                    y * self.cell_size,
                    self.cell_size,
                    self.cell_size
                )
                pygame.draw.rect(screen, (200, 200, 200), rect, 1)

                block = self.grid[y][x]
                if block:
                    # unpack tuple or treat as no-rotation
                    if isinstance(block, tuple):
                        surf, rot = block
                    else:
                        surf, rot = block, 0

                    # scale then rotate around center
                    tile = pygame.transform.scale(surf, (self.cell_size, self.cell_size))
                    if rot:
                        tile = pygame.transform.rotate(tile, rot)

                    # center the rotated tile in the cell
                    blit_rect = tile.get_rect(center=(
                        x * self.cell_size + self.cell_size/2,
                        y * self.cell_size + self.cell_size/2
                    ))
                    screen.blit(tile, blit_rect.topleft)



class TrackEditor:
    def __init__(self, screen):
        self.screen = screen
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()

        # reserve bottom UI panel for palette
        self.palette_height   = 80
        # grid area height = screen height minus palette
        self.grid_pixel_size = min(self.screen_width - self.palette_height, self.screen_height - self.palette_height)

        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
    
        self.grid_size = self.get_grid_size()
        self.init_grid()

        self.selected_rotation = 0   # current rotation in degrees


        # after loading asset_images, add:
        sheet = pygame.image.load(os.path.join(ASSETS_DIR, 'TrackPieces.png')).convert_alpha()
        tile_w = sheet.get_width() // 3
        tile_h = sheet.get_height() // 3

        # indices: 0=no walls, 1=one wall, 2=opposite walls,
        # 3=adjacent walls, 4=90° curve, 5=45° curve
        road_tiles = [sheet.subsurface(pygame.Rect(col*tile_w, row*tile_h, tile_w, tile_h)).copy()
                    for row in range(3) for col in range(3)]
    
        """
        self.blocks = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
        ]
        """
        self.blocks = road_tiles # Use the loaded road tiles

        self.selected_block = self.blocks[0]  # Start with the first block selected
        # place palette panel at bottom, full width
        self.palette_rect   = pygame.Rect(
           0,
           self.grid_pixel_size,
           self.screen_width,
           self.palette_height
        )

        self.spawn_point    = None        # will hold (cell_x, cell_y)
        self.finish_line    = []          # will hold exactly two points [(x1,y1),(x2,y2)]
        self.checkpoint_lines   = []     # list of [ (x1,y1),(x2,y2) ] segments
        self._current_checkpoint = []     # temp storage for the two clicks
        self.edit_mode      = 'block'     # modes: 'block', 'spawn', 'finish', 'checkpoint'


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
                    elif event.key == pygame.K_r and self.selected_block:
                        # rotate by 90° each press
                        self.selected_rotation = (self.selected_rotation + 90) % 360
                    elif event.key == pygame.K_p:
                        self.edit_mode = 'spawn'
                    elif event.key == pygame.K_f:
                        self.edit_mode = 'finish'
                        self.finish_line = []          # reset finish‐line points
                    elif event.key == pygame.K_k:
                        self.edit_mode = 'checkpoint'
                        self._current_checkpoint = []


            self.screen.fill((200, 200, 200))  # Light gray background
            
            # Calculate the position to center the grid
            # center horizontally, top‐align so palette sits below
            grid_x = (self.screen_width  - self.grid_pixel_size) // 2
            grid_y = 0
            
            # Create a surface for the grid
            grid_surface = pygame.Surface((self.grid_pixel_size, self.grid_pixel_size))
            grid_surface.fill((0, 255, 0))  # Green background for the grid
            self.grid.draw(grid_surface)

            cell = self.grid.cell_size

            # spawn point
            if self.spawn_point:
                sx, sy = self.spawn_point
                cx = sx * cell + cell // 2
                cy = sy * cell + cell // 2
                pygame.draw.circle(grid_surface, (0, 0, 255), (cx, cy), cell // 3, 2)

            # finish line
            if len(self.finish_line) == 2:
                (x1, y1), (x2, y2) = self.finish_line
                p1 = (x1 * cell + cell // 2, y1 * cell + cell // 2)
                p2 = (x2 * cell + cell // 2, y2 * cell + cell // 2)
                pygame.draw.line(grid_surface, (255, 255, 255), p1, p2, max(1, cell // 10))

            # draw saved checkpoint lines
            for (x1,y1),(x2,y2) in self.checkpoint_lines:
                p1 = (x1*cell + cell//2, y1*cell + cell//2)
                p2 = (x2*cell + cell//2, y2*cell + cell//2)
                pygame.draw.line(grid_surface, (255,165,0), p1, p2, max(1,cell//10))

            # if you’re in the middle of placing one, show the “rubber‐band”:
            if self.edit_mode=='checkpoint' and len(self._current_checkpoint)==1:
                (x1,y1) = self._current_checkpoint[0]
                p1 = (x1*cell + cell//2, y1*cell + cell//2)
                mouse_x, mouse_y = pygame.mouse.get_pos()
                # convert screen mouse to grid_surface coords:
                rel_x = mouse_x - grid_x
                rel_y = mouse_y - grid_y
                pygame.draw.line(grid_surface, (255,200,0), p1, (rel_x,rel_y), max(1,cell//10))
            
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
            grid_x = (self.screen_width  - self.grid_pixel_size) // 2
            grid_y = 0
            
            if grid_x <= pos[0] < grid_x + self.grid_pixel_size and grid_y <= pos[1] < grid_y + self.grid_pixel_size:
                cell_x, cell_y = self.grid.get_cell(pos[0] - grid_x, pos[1] - grid_y)
                if 0 <= cell_x < self.grid_size and 0 <= cell_y < self.grid_size:
                    # … compute cell_x, cell_y …
                    if button == 1:  # left‐click
                        if self.edit_mode == 'spawn':
                            self.spawn_point = (cell_x, cell_y)
                            self.edit_mode   = 'block'

                        elif self.edit_mode == 'finish':
                            self.finish_line.append((cell_x, cell_y))
                            if len(self.finish_line) >= 2:
                                self.edit_mode = 'block'

                        elif self.edit_mode == 'checkpoint':
                            # record one end
                            self._current_checkpoint.append((cell_x, cell_y))
                            # once we have two, store it and reset
                            if len(self._current_checkpoint) == 2:
                                self.checkpoint_lines.append(tuple(self._current_checkpoint))
                                self._current_checkpoint = []
                                self.edit_mode = 'block'

                        else:  # normal block mode
                            # new
                            if self.selected_block:
                                self.grid.place_block(
                                    cell_x, cell_y,
                                    self.selected_block,
                                    self.selected_rotation
                                )

                            else:
                                self.grid.remove_block(cell_x, cell_y)
                    elif button == 3:  # Right click
                        self.grid.remove_block(cell_x, cell_y)


    def handle_palette_click(self, pos):
        x, y = pos
        if not self.palette_rect.collidepoint(x, y):
            return

        total      = len(self.blocks)
        slot_width = self.palette_rect.width // total
        rel_x      = x - self.palette_rect.x
        index      = rel_x // slot_width

        if 0 <= index < total:
            self.selected_block = self.blocks[index]
        # no eraser slot any more


    def draw_block_palette(self):
        # background for palette
        pygame.draw.rect(self.screen, (245, 245, 245), self.palette_rect)

        # compute square slot size & horizontal layout
        total      = len(self.blocks)
        slot_width = self.palette_rect.width // total
        padding    = 8
        slot_size  = self.palette_rect.height - padding*2

        for i, tile in enumerate(self.blocks):
            # slot rect in the palette
            x0 = self.palette_rect.x + i * slot_width + padding
            y0 = self.palette_rect.y + padding
            rect = pygame.Rect(x0, y0, slot_size, slot_size)

            # choose surf → rotate if it’s the selected one
            if tile == self.selected_block:
                surf = pygame.transform.rotate(tile, self.selected_rotation)
            else:
                surf = tile

            # scale to fit the square slot
            tile_surf = pygame.transform.scale(surf, (slot_size, slot_size))
            self.screen.blit(tile_surf, rect.topleft)

            # highlight selected
            if tile == self.selected_block:
                pygame.draw.rect(self.screen, (255, 255, 175), rect, 2)



    def draw_instructions(self):
        text = self.font.render("Left-click to place blocks", True, (0, 0, 0))
        self.screen.blit(text, (10, 10))
        text = self.font.render("Right-click to remove blocks", True, (0, 0, 0))
        self.screen.blit(text, (10, 30))
        text = self.font.render("Press 'S' to save track", True, (0, 0, 0))
        self.screen.blit(text, (10, 50))
        text = self.font.render("Press 'L' to load track", True, (0, 0, 0))
        self.screen.blit(text, (10, 70))
        text = self.font.render("Press 'P' to place spawn point", True, (0, 0, 0))
        self.screen.blit(text, (10, 90))
        text = self.font.render("Press 'F' to place finish line", True, (0, 0, 0))
        self.screen.blit(text, (10, 110))
        text = self.font.render("Press 'K' to place checkpoint", True, (0, 0, 0))
        self.screen.blit(text, (10, 130))
        text = self.font.render("Press 'Esc' to return to menu", True, (0, 0, 0))
        self.screen.blit(text, (10, 150))

    def save_track(self):
        #file_name = input("Enter file name: ")
        box = pygame.Rect(self.screen.get_width()//2 - 150, self.screen.get_height()//2 - 20, 300, 40)
        file_name = get_text_input(self.screen, "Enter file name: ", default_font, box)
        with open(file_name + '.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            # Write the grid size as the first row
            writer.writerow([self.grid_size])

            if self.spawn_point:
                x, y = self.spawn_point
                writer.writerow(['spawn', x, y])

            if len(self.finish_line) == 2:
                x1, y1 = self.finish_line[0]
                x2, y2 = self.finish_line[1]
                writer.writerow(['finish', x1, y1, x2, y2])

            for (x1,y1),(x2,y2) in self.checkpoint_lines:
                writer.writerow(['checkpoint', x1, y1, x2, y2])

            # ... then your existing loop that writes each block row ...

            for y in range(self.grid_size):
                for x in range(self.grid_size):
                    block = self.grid.get_block(x, y)
                    if block:
                        surf, rot = block                      # unpack Surface & rotation
                        idx     = self.blocks.index(surf)      # find its palette index
                        writer.writerow([x, y, idx, rot])

    def load_track(self):
        #file_name = input("Enter file name: ")
        box = pygame.Rect(self.screen.get_width()//2 - 150, self.screen.get_height()//2 - 20, 300, 40)
        file_name = get_text_input(self.screen, "Enter file name: ", default_font, box)
        if os.path.exists(file_name + '.csv'):
            with open(file_name + '.csv', 'r') as file:
                reader = csv.reader(file)
                # reset metadata
                self.spawn_point = None
                self.finish_line = []
                self.checkpoints = []

                # first row: grid size
                self.grid_size = int(next(reader)[0])
                self.init_grid()

                for row in reader:
                    tag = row[0]
                    if tag == 'spawn':
                        self.spawn_point = (int(row[1]), int(row[2]))
                    elif tag == 'finish':
                        x1, y1, x2, y2 = map(int, row[1:])
                        self.finish_line = [(x1, y1), (x2, y2)]
                    elif tag == 'checkpoint':
                        x1,y1,x2,y2 = map(int, row[1:])
                        self.checkpoint_lines.append(((x1,y1),(x2,y2)))
                    else:
                        x, y, idx, rot = map(int, row)
                        surf = self.blocks[idx]
                        self.grid.place_block(x, y, surf, rot)


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
        self.steer_speed = math.radians(200)  # how fast you turn the wheels (rad/sec)
        self.mass = 1200             # mass in arbitrary units
        self.Cd = 0.425              # drag coefficient
        self.Crr = 2000              # rolling resistance coeff
        self.Crr_normal = self.Crr
        self.Crr_offtrack = self.Crr * 5.0  # double rolling resistance when off‐road

        # per‐terrain Crr values
        self.Crr_blue     = self.Crr_normal * Crr_BLUE_MULT
        self.Crr_grass    = self.Crr_normal * Crr_GRASS_MULT
        self.Crr_gravel   = self.Crr_normal * Crr_GRAVEL_MULT
        self.Crr_sand     = self.Crr_normal * Crr_SAND_MULT

        # dynamic state
        self.velocity = 0.0          # forward speed (px/sec)
        self.yaw = math.radians(self.angle)  # vehicle heading (rad)
        self.steer = 0.0             # current front‐wheel steer angle (rad)

        # inputs
        self.throttle = 0.0          # in [0..1]
        self.brake_input = 0.0       # in [0..1]

        # maximum longitudinal forces (engine drives forward, brakes drive backward)
        self.max_engine_force = 1500000.0    # adjust to taste
        self.max_brake_force  = -2000000.0   # negative so braking produces a backward force
        
        # for collision rollback
        self.prev_x, self.prev_y, self.prev_yaw = x, y, self.yaw

            # in Car.__init__:
        self.reverse_delay  = 0.2   # seconds to wait at zero before reversing
        self.time_since_stop = 0.0  # timer accumulator

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
        # save previous in case we need to roll back on collision
        self.prev_x, self.prev_y, self.prev_yaw = self.x, self.y, self.yaw

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
        # choose a per‐car sprite if assigned, else fallback
        base_sprite = getattr(self, 'sprite_raw', CAR_IMAGE_RAW)
        # scale it to the car’s logical size
        sprite = pygame.transform.scale(
            base_sprite,
            (int(self.width), int(self.height))
        )
        # rotate around center
        rotated = pygame.transform.rotate(sprite, self.angle)
        rect    = rotated.get_rect(center=(self.x, self.y))
        screen.blit(rotated, rect.topleft)

    def handle_collision(self):
        # go back to last good state and stop
        self.x, self.y, self.yaw = self.prev_x, self.prev_y, self.prev_yaw
        self.velocity = 0
        # keep public angle in sync
        self.angle = -math.degrees(self.yaw)

class Track:
    def __init__(self, name):
        self.name = name
        self.blocks = []
        self.spawn_point   = None
        self.finish_line   = []
        self.grid_size = 0
        self.block_size = 0
        self.screen_size = 800  # We'll use a square screen
        self.checkpoint_lines = []

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

                # --- NEW: grab grid size from the very first row ---
                first_row = next(reader)
                self.grid_size  = int(first_row[0])
                self.block_size = self.screen_size // self.grid_size

                # now clear and init all your lists
                self.blocks      = []
                self.spawn_point = None
                self.finish_line = []
                self.checkpoints_lines = []

                # existing loop over the rest of the rows
                for row in reader:
                    tag = row[0]
                    if tag == 'spawn':
                        self.spawn_point = (int(row[1]), int(row[2]))
                    elif tag == 'finish':
                        x1, y1, x2, y2 = map(int, row[1:])
                        self.finish_line = [(x1, y1), (x2, y2)]
                    elif tag == 'checkpoint':
                        # —or— if you moved to line‐based checkpoints:
                        x1, y1, x2, y2 = map(int, row[1:])
                        self.checkpoint_lines.append([[x1,y1],[x2,y2]])
                    else:
                        x, y, idx, rot = map(int, row)
                        self.blocks.append((x, y, idx, rot))

            print(f"Successfully loaded track '{file_name}' with {len(self.blocks)} blocks")
            print(f"Grid size: {self.grid_size}, Block size: {self.block_size}")

        except FileNotFoundError:
            print(f"Track file '{file_name}' not found.")
        except Exception as e:
            print(f"Error loading track: {e}")


    def draw(self, screen):
        # Fill the background with green
        screen.fill((0, 200, 0))  # Green color
        
        for x, y, idx, rot in self.blocks:
            # 1) pull the original sprite
            tile = road_tiles[idx]

            # 2) scale it down to your block size
            tile = pygame.transform.scale(
                tile,
                (self.block_size, self.block_size)
            )

            # 3) then rotate (if rot ≠ 0)
            if rot:
                tile = pygame.transform.rotate(tile, rot)

            # 4) compute its centered position in the grid cell
            blit_rect = tile.get_rect(center=(
                x * self.block_size + self.block_size/2,
                y * self.block_size + self.block_size/2
            ))

            # 5) draw it
            screen.blit(tile, blit_rect.topleft)
        
        # Draw grid lines for debugging
        
        #for i in range(self.grid_size + 1):
         #   pygame.draw.line(screen, (0, 0, 0), (i * self.block_size, 0), (i * self.block_size, self.screen_size))
          #  pygame.draw.line(screen, (0, 0, 0), (0, i * self.block_size), (self.screen_size, i * self.block_size))
            

    def get_car_size(self):
        # Make the car size proportional to the grid
        car_width = self.block_size * 0.5  # 50% of a block width
        car_height = self.block_size * 0.32  # 25% of a block height
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
            if self.last_colors[name] is None:
                self.last_colors[name] = (0, 0, 0)  # Initialize with black
                continue
            colorDifference = abs(color[0] - (self.last_colors[name])[0]) + abs(color[1] - (self.last_colors[name])[1]) + abs(color[2] - (self.last_colors[name])[2])
            if colorDifference > 3:
                #print(f"Listener '{name}' detected new color: {color}")
                self.last_colors[name] = color
    def update(self, colors):

        for name, color in colors.items():
            colorDifference = abs(color[0] - self.last_colors[name][0]) + abs(color[1] - self.last_colors[name][1]) + abs(color[2] - self.last_colors[name][2])
            if colorDifference > 3:
                #print(f"Listener '{name}' detected new color: {color}")
                self.last_colors[name] = color

    def draw_debug(self, screen):
        for _, x, y in self.get_listener_positions():
            pygame.draw.circle(screen, (255, 0, 0), (x, y), 2)

    def check_collision(self, colors):
        """
        Returns True if *any* listener sees grass (RGB exactly (0,200,0)),
        meaning we’ve left the road.
        """
        for name, color in colors.items():
            if color[:3] == (0, 200, 0):
                #print(f"Listener '{name}' detected grass color: {color}")
                return True
        return False
    
    def check_wall_collision(self, colors):
        """
        Returns True if any non-wheel listener (body) sees the wall color (255,0,0).
        """
        for name, col in colors.items():
            if 'wheel' not in name and col[:3] == (255, 0, 0):
                return True
        return False

    def any_wheel_offtrack(self, colors):
        """
        Returns True if any wheel listener sees grass (0,200,0).
        """
        for name, col in colors.items():
            if 'wheel' in name and col[:3] == (0, 200, 0):
                return True
        return False

class RaceManager:
    def __init__(self, track, font):
        self.track            = track
        self.font             = font
        self.lap_count        = 0
        self.lap_times        = []
        self.current_cp_idx   = 0
        self.lap_start        = pygame.time.get_ticks() / 1000.0
        self.lap_start      = pygame.time.get_ticks() / 1000.0
        self.best_lap       = None

    def update(self, car):
        """Call this at each sub-step to catch fast crossings."""
        bs   = self.track.block_size
        prev = (car.prev_x, car.prev_y)
        curr = (car.x, car.y)

        # 1) In-order checkpoint crossing
        if self.current_cp_idx < len(self.track.checkpoint_lines):
            x1,y1 = self.track.checkpoint_lines[self.current_cp_idx][0]
            x2,y2 = self.track.checkpoint_lines[self.current_cp_idx][1]
            p1 = (x1*bs + bs/2, y1*bs + bs/2)
            p2 = (x2*bs + bs/2, y2*bs + bs/2)
            if self._crossed(prev, curr, p1, p2):
                self.current_cp_idx += 1
                print(f"Checkpoint {self.current_cp_idx} cleared")

        # 2) Only after *all* checkpoints, check finish-line for a lap
        elif self.current_cp_idx == len(self.track.checkpoint_lines) and len(self.track.finish_line) == 2:
            (f1x,f1y),(f2x,f2y) = self.track.finish_line
            f1 = (f1x*bs + bs/2, f1y*bs + bs/2)
            f2 = (f2x*bs + bs/2, f2y*bs + bs/2)
            if self._crossed(prev, curr, f1, f2):
                now = pygame.time.get_ticks() / 1000.0
                lap_duration = now - self.lap_start
                # record exactly once
                self.lap_times.append(lap_duration)
                # update best if needed
                if self.best_lap is None or lap_duration < self.best_lap:
                    self.best_lap = lap_duration
                self.lap_start = now
                self.lap_count += 1
                self.current_cp_idx = 0
                print(f"Lap {self.lap_count} complete: {lap_duration:.2f}s")

    def draw(self, screen, x_off=10, y_off=10, label=None):
        """
        Draw the lap UI at (x_off, y_off). 
        If label is provided, it prefixes the lap display.
        """
        line_h = 30  # vertical spacing

        # 1) Lap count (with optional label)
        if label:
            title = f"{label} Lap: {self.lap_count}"
        else:
            title = f"Lap: {self.lap_count}"
        lap_surf = self.font.render(title, True, (0,0,0))
        screen.blit(lap_surf, (x_off, y_off))

        # 2) Current lap timer
        now   = pygame.time.get_ticks() / 1000.0
        curr  = now - self.lap_start
        curr_surf = self.font.render(f"Current: {curr:.2f}s", True, (0,0,0))
        screen.blit(curr_surf, (x_off, y_off + line_h))

        # 3) Last lap time
        if self.lap_times:
            last = self.lap_times[-1]
            last_surf = self.font.render(f"Last: {last:.2f}s", True, (0,0,0))
            screen.blit(last_surf, (x_off, y_off + line_h * 2))

        # 4) Best lap time
        if self.best_lap is not None:
            best_surf = self.font.render(f"Best: {self.best_lap:.2f}s", True, (0,0,0))
            screen.blit(best_surf, (x_off, y_off + line_h * 3))


    @staticmethod
    def _crossed(p0, p1, a, b):
        """
        Returns True if the movement from p0→p1 crosses the line segment a→b.
        """
        x0, y0 = p0
        x1, y1 = p1
        ax, ay = a
        bx, by = b

        # signed distance from each point to the line
        side0 = (x0 - ax) * (by - ay) - (y0 - ay) * (bx - ax)
        side1 = (x1 - ax) * (by - ay) - (y1 - ay) * (bx - ax)

        return side0 * side1 < 0

class Controller:
    def get_actions(self, car, keys=None):
        # returns (throttle, brake_input, steer_target)
        raise NotImplementedError
    
class KeyboardController(Controller):
    def __init__(self, scheme):
        self.scheme          = scheme
        self.time_since_stop = 0.0

    def get_actions(self, car, keys, dt):
        up    = self.scheme['up']
        down  = self.scheme['down']
        left  = self.scheme['left']
        right = self.scheme['right']

        # —— reverse-delay timer ——
        if keys[down] and car.velocity <= 0:
            self.time_since_stop += dt
        else:
            self.time_since_stop = 0.0

        # —— throttle / brake / reverse ——
        if keys[up]:
            throttle, brake_input =  1.0, 0.0

        elif keys[down]:
            if car.velocity > 0:
                throttle, brake_input =  0.0, 1.0
            elif self.time_since_stop >= car.reverse_delay:
                throttle, brake_input = -1.0, 0.0
            else:
                throttle, brake_input =  0.0, 0.0

        else:
            throttle, brake_input =  0.0, 0.0

        # —— steering ——
        if keys[left]:
            steer_target =  car.max_steer
        elif keys[right]:
            steer_target = -car.max_steer
        else:
            steer_target =  0.0

        return throttle, brake_input, steer_target


class Menu:
    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.Font(None, 36)
        self.options = ["Track Editor", "Load Game", "Quit"]
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

def compute_spawns(spawn_cell, num, collide, track):
    cx, cy = spawn_cell
    bs = track.block_size
    center_x = cx * bs + bs/2
    center_y = cy * bs + bs/2

    # Determine track “forward” direction from finish_line if available
    if hasattr(track, 'finish_line') and len(track.finish_line) == 2:
        fx1, fy1 = track.finish_line[0]
        fx2, fy2 = track.finish_line[1]
        vertical = (fy1 == fy2)
        # sign = +1 means “away from finish”, −1 “toward finish”
        if vertical:
            sign = 1 if cy > fy1 else -1
        else:
            sign = 1 if cx > fx1 else -1
    else:
        # No finish line: assume horizontal track, push cars “down” as default
        vertical = False
        sign = 1

    spawns = []
    if not collide:
        # all cars stack on the spawn tile
        spawns = [(center_x, center_y)] * num
    else:
        offset = bs * 0.25  # quarter‐block corner offset
        for i in range(num):
            layer  = i // 2      # 0 = inner row, 1 = one back, etc.
            corner = i %  2      # 0 = +xy, 1 = -xy

            # start with corner offset
            dx =  offset if corner == 0 else -offset
            dy =  offset if corner == 0 else -offset

            # then push back by `layer` full blocks
            behind = layer * bs * sign
            if vertical:
                dy += behind
            else:
                dx += behind

            spawns.append((center_x + dx, center_y + dy))

    return spawns


def drive_car(screen, track_name):
    track = Track(track_name)
    if not track.blocks:  # If no blocks were loaded, return to menu
        print("Failed to load track. Returning to menu.")
        return "MENU"
    
    # right after you load the track and before setting screen_size…

    screen_size = track.get_screen_size()
    screen = pygame.display.set_mode(screen_size)  # Resize the screen
    
    pygame.font.init()
    default_font = pygame.font.Font(None, 32)
    # ask how many cars

    box = pygame.Rect(screen.get_width()//2-150, screen.get_height()//2-20, 300, 40)
    num = int(get_text_input(screen, "Number of cars: ", default_font, box))
    num_cars = max(1, min(num, 10))   # clamp between 1 and 10

    # ask if cars should collide
    box = pygame.Rect(screen.get_width()//2-150, screen.get_height()//2-20, 300, 40)
    txt = get_text_input(screen, "Car collisions? (y/n): ", default_font, box)
    collide_cars = txt.strip().lower().startswith('y')
    
    car_width, car_height = track.get_car_size()

    # Place the car at the spawn point on the screen

    """ Old Spawn Point Code

    if hasattr(track, 'spawn_point') and track.spawn_point:
        gx, gy = track.spawn_point
        car_x = gx * track.block_size + track.block_size / 2 - car_width / 2
        car_y = gy * track.block_size + track.block_size / 2 - car_height / 2
    else:
        car_x = (screen_size[0] - car_width) / 2
        car_y = (screen_size[1] - car_height) / 2
        """

    # New Spawn Point Code
    spawns = compute_spawns(track.spawn_point, num_cars, collide_cars, track)
    cars   = [Car(x, y, car_width, car_height) for x,y in spawns]

    # load up to 8 car‐color sprites
    car_sprite_images = []
    for i in range(8):
        path = os.path.join(ASSETS_DIR, f"Car{i+1}.png")
        img  = pygame.image.load(path).convert_alpha()
        car_sprite_images.append(img)

    # now assign each Car instance its own raw sprite
    for idx, c in enumerate(cars):
        # pick the i-th sprite cycling through the 8
        raw_img = car_sprite_images[idx % len(car_sprite_images)]
        c.sprite_raw = raw_img

    default_font = pygame.font.Font(None, 32)
    managers = [RaceManager(track, default_font) for _ in cars]

        # for each human‐driven car, give it a KeyboardController
            
        # simple keyboard mappings for up to 4 humans
    control_schemes = [
        {'up': pygame.K_UP,    'down': pygame.K_DOWN,
        'left': pygame.K_LEFT,'right': pygame.K_RIGHT},
        {'up': pygame.K_w,     'down': pygame.K_s,
        'left': pygame.K_a,   'right': pygame.K_d},
        {'up': pygame.K_t,     'down': pygame.K_g,
        'left': pygame.K_f,   'right': pygame.K_h},
        {'up': pygame.K_i,     'down': pygame.K_k,
        'left': pygame.K_j,   'right': pygame.K_l},
    ]
    # for more cars you can recycle schemes or leave them unresponsive (for AI later)

    controllers = [
        KeyboardController(control_schemes[i % len(control_schemes)])
        for i in range(len(cars))
    ]

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

        # throttle & brake as normalized inputs
        keys = pygame.key.get_pressed()

        # update with real physics
        # 1) advance the car
                # build a static surface with track + finish + checkpoints
        track_surface = pygame.Surface(screen_size)

        # 1a) draw base track
        track_surface.fill((0, 200, 0))
        track.draw(track_surface)

        # 1b) overlay finish line
        bs = track.block_size
        if getattr(track, 'finish_line', None) and len(track.finish_line) == 2:
            (x1, y1), (x2, y2) = track.finish_line
            p1 = (x1*bs + bs//2, y1*bs + bs//2)
            p2 = (x2*bs + bs//2, y2*bs + bs//2)
            pygame.draw.line(track_surface, (255,255,255), p1, p2, max(1, bs//10))

        # 1c) overlay checkpoint segments
        for (cx1, cy1), (cx2, cy2) in getattr(track, 'checkpoint_lines', []):
            q1 = (cx1*bs + bs//2, cy1*bs + bs//2)
            q2 = (cx2*bs + bs//2, cy2*bs + bs//2)
            pygame.draw.line(track_surface, (255,165,0), q1, q2, max(1, bs//10))

        # determine how many sub-steps so max move per step is ≤ half a cell
        max_dist = track.block_size * 0.05
        num_steps = max(1, int(abs(100 * dt) / max_dist) + 1)
        sub_dt = dt / num_steps

        for _ in range(num_steps):
            # advance by a fraction of dt
            # update each car’s physics & sensors
            for idx, (mgr, c) in enumerate(zip(managers, cars)):
                # 1) get human or AI inputs
                thr, brk, steer = controllers[idx].get_actions(c, keys, sub_dt)
                c.throttle     = thr
                c.brake_input  = brk
                c.steer_target = steer

                # 2) update the car’s physics
                c.update(sub_dt)

                # sample sensors
                positions = c.collision_detector.get_listener_positions()
                colors = {}
                for name, x, y in positions:
                    x = max(0, min(x, screen.get_width()-1))
                    y = max(0, min(y, screen.get_height()-1))
                    colors[name] = track_surface.get_at((x, y))
                c.collision_detector.update_colors(colors)

                if c.collision_detector.check_wall_collision(colors):
                    # crashes on walls as before
                    c.handle_collision()

                else:
                    # look only at the wheel sensors for terrain
                    wheel_colors = [col[:3] for name,col in colors.items() if 'wheel' in name]

                    # sand = heaviest
                    if any(col == SAND_COLOR     for col in wheel_colors):
                        c.Crr = c.Crr_sand

                    # then gravel
                    elif any(col == GRAVEL_COLOR for col in wheel_colors):
                        c.Crr = c.Crr_gravel

                    # then grass
                    elif any(col == GRASS_COLOR  for col in wheel_colors):
                        c.Crr = c.Crr_grass

                    # then blue curb (slight)
                    elif any(col == CURB_BLUE_COLOR for col in wheel_colors):
                        c.Crr = c.Crr_blue

                    # otherwise normal track
                    else:
                        c.Crr = c.Crr_normal

                # — after screen = pygame.display.set_mode(screen_size) —

                pygame.font.init()
                default_font = pygame.font.Font(None, 32)

                # 3) update lap logic
                mgr.update(c)


            if collide_cars:
                for i in range(len(cars)):
                    for j in range(i+1, len(cars)):
                        # simple AABB based on width/height
                        r1 = pygame.Rect(
                            cars[i].x - cars[i].width/2,
                            cars[i].y - cars[i].height/2,
                            cars[i].width, cars[i].height
                        )
                        r2 = pygame.Rect(
                            cars[j].x - cars[j].width/2,
                            cars[j].y - cars[j].height/2,
                            cars[j].width, cars[j].height
                        )
                        if r1.colliderect(r2):
                            cars[i].handle_collision()
                            cars[j].handle_collision()

        # show the pre-rendered track + lines
        screen.blit(track_surface, (0, 0))

        for idx, (mgr, c) in enumerate(zip(managers, cars)):
            # stagger UIs down the left edge
            y0 = 10 + idx * 110
            label = f"Car {idx+1}:"
            mgr.draw(screen, x_off=10, y_off=y0, label=label)
            c.draw(screen)
        
        pygame.display.flip()
        clock.tick(60)



def main():
    pygame.init()
    screen = pygame.display.set_mode((800, 800))

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

