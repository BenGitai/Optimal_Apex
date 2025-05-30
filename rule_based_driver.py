import math
from RacingAI import Track, Car, RaceManager

class HeuristicController:
    """
    A rule-based controller that drives using LIDAR and checkpoint info.
    """
    def __init__(self, track: Track, manager: RaceManager, track_surface=None, car = None):
        self.track = track
        self.manager = manager
        # LIDAR settings
        self.num_rays = 11
        self.fov = math.pi * 1
        self.max_dist = None  # will be set based on car width
        self.step = 4
        # Steering deadzone
        self.dead_zone = 0.1
        # Threshold to consider path blocked
        self.block_thresh = None  # set in get_actions
        self.track_surface = track_surface
        self.car = car

    def get_actions(self, car: Car, keys=None, dt: float = 0.0):
        # Initialize max_dist and block_thresh on first call
        if car is not None:
            self.car = car
        if self.max_dist is None:
            self.max_dist = self.car.width * 10
            self.block_thresh = self.car.width * 1.5

        # 1) Sense environment via LIDAR
        rays = self.car.get_lidar(
            self.track_surface,
            num_rays=self.num_rays,
            fov=self.fov,
            max_dist=self.max_dist,
            step=self.step
        )
        # Central ray index
        center_idx = self.num_rays // 2
        forward_dist = rays[center_idx]

        print(self.car)

        # Check next checkpoint direction
        dist_to_cp, ang_to_cp = self.manager.get_next_checkpoint_info(self.car)

        # 2) Decide steering
        # If path ahead is blocked, choose direction with more clearance
        if forward_dist < self.block_thresh:
            left_clear  = rays[0] + rays[1]
            right_clear = rays[-1] + rays[-2]
            steer_dir = -1.0 if left_clear < right_clear else 1.0
            steer_cmd = steer_dir
        else:
            # steer toward checkpoint if angle is large
            norm_ang = (ang_to_cp + math.pi) % (2*math.pi) - math.pi
            if abs(norm_ang) < self.dead_zone:
                steer_cmd = 0.0
            else:
                steer_cmd = max(-1.0, min(1.0, norm_ang / self.car.max_steer))

        # Apply dead zone
        if abs(steer_cmd) < self.dead_zone:
            steer_cmd = 0.0

        # 3) Throttle / brake logic
        # Always accelerate if clear ahead and roughly pointing to checkpoint
        if forward_dist > self.block_thresh and abs(norm_ang) < math.pi/4:
            throttle = 1.0
            brake = 0.0
        else:
            throttle = 0.5
            brake = 0.0

        return throttle, brake, steer_cmd
