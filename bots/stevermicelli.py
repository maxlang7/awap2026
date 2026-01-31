import random
from collections import deque
from typing import Tuple, Optional, List

import time

from game_constants import Team, TileType, FoodType, ShopCosts
from robot_controller import RobotController
from item import Pan, Plate, Food

# Global State Variables (N = Noodles, M = Meat, P = Plate):
INIT, BUY_PAN, BUY_M, M_ON_COUNTER, CHOP_M = 0, 1, 2, 3, 4
PICK_UP_CHOPPED_M, MEAT_IN_PAN = 5, 6
BUY_P = 7
P_ON_COUNTER = 8
BUY_N = 9
N_TO_P = 10
WAIT_FOR_M = 11
M_TO_P = 12
PICK_UP_COMPLETE_P = 13
SUBMIT_DISH = 14
TRASH = 15

class BotPlayer:
    def __init__(self, map_copy):
        self.map = map_copy
        self.assembly_counter = None
        self.cooker_loc = None
        self.my_bot_id = None

        self.state = INIT

    def get_bfs_path(self, controller: RobotController, start: Tuple[int, int], target_predicate) -> Optional[Tuple[int, int]]:
        queue = deque([(start, [])])
        visited = set([start])
        w, h = self.map.width, self.map.height

        while queue:
            (curr_x, curr_y), path = queue.popleft()
            tile = controller.get_tile(controller.get_team(), curr_x, curr_y)
            if target_predicate(curr_x, curr_y, tile):
                if not path: return (0, 0)
                return path[0]

            for dx in [0, -1, 1]:
                for dy in [0, -1, 1]:
                    if dx == 0 and dy == 0: continue
                    nx, ny = curr_x + dx, curr_y + dy
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                        if controller.get_map().is_tile_walkable(nx, ny):
                            visited.add((nx, ny))
                            queue.append(((nx, ny), path + [(dx, dy)]))
        return None

    def move_towards(self, controller: RobotController, bot_id: int, target_x: int, target_y: int) -> bool:
        bot_state = controller.get_bot_state(bot_id)
        bx, by = bot_state['x'], bot_state['y']
        def is_adjacent_to_target(x, y, tile):
            return max(abs(x - target_x), abs(y - target_y)) <= 1
        if is_adjacent_to_target(bx, by, None): return True
        step = self.get_bfs_path(controller, (bx, by), is_adjacent_to_target)
        if step and (step[0] != 0 or step[1] != 0):
            controller.move(bot_id, step[0], step[1])
            return False
        return False

    def find_nearest_tile(self, controller: RobotController, bot_x: int, bot_y: int, tile_name: str) -> Optional[Tuple[int, int]]:
        best_dist = 9999
        best_pos = None
        m = controller.get_map()
        for x in range(m.width):
            for y in range(m.height):
                tile = m.tiles[x][y]
                if tile.tile_name == tile_name:
                    dist = max(abs(bot_x - x), abs(bot_y - y))
                    if dist < best_dist:
                        best_dist = dist
                        best_pos = (x, y)
        return best_pos

    def play_turn(self, controller: RobotController):
        # For testing
        time.sleep(0.3)
        my_bots = controller.get_team_bot_ids()
        if not my_bots: return

        self.my_bot_id = my_bots[0]
        bot_id = self.my_bot_id

        bot_info = controller.get_bot_state(bot_id)
        bx, by = bot_info['x'], bot_info['y']

        if self.assembly_counter is None:
            self.assembly_counter = self.find_nearest_tile(controller, bx, by, "COUNTER")
        if self.cooker_loc is None:
            self.cooker_loc = self.find_nearest_tile(controller, bx, by, "COOKER")

        if not self.assembly_counter or not self.cooker_loc: return

        cx, cy = self.assembly_counter
        kx, ky = self.cooker_loc

<<<<<<< HEAD
        if self.state in [BUY_M, BUY_P, BUY_N] and bot_info.get('holding'):
            self.state = TRASH
=======
        # Preliminary check If the bot is holding something unexpected during
        # -states 2, 8, or 10 (when it should buy items), it goes to trash state to clear its hands.
        if self.state in [2, 8, 10] and bot_info.get('holding'):
            self.state = 16
>>>>>>> 1d8ed89398682aae1b3fc54baa28fca74deb2843

        #state 0: init + checking the pan
        if self.state == INIT:
            tile = controller.get_tile(controller.get_team(), kx, ky)
            if tile and isinstance(tile.item, Pan):
                self.state = BUY_M
            else:
                self.state = BUY_PAN

        #state 1: buy pan
        elif self.state == BUY_PAN:
            holding = bot_info.get('holding')
            if holding: # assume it's the pan
                if self.move_towards(controller, bot_id, kx, ky):
                    if controller.place(bot_id, kx, ky):
                        self.state = BUY_M
            else:
                shop_pos = self.find_nearest_tile(controller, bx, by, "SHOP")
                if not shop_pos: return
                sx, sy = shop_pos
                if self.move_towards(controller, bot_id, sx, sy):
                    if controller.get_team_money() >= ShopCosts.PAN.buy_cost:
                        controller.buy(bot_id, ShopCosts.PAN, sx, sy)

        #state 2: buy meat
        elif self.state == BUY_M:
            shop_pos = self.find_nearest_tile(controller, bx, by, "SHOP")
            sx, sy = shop_pos
            if self.move_towards(controller, bot_id, sx, sy):
                if controller.get_team_money() >= FoodType.MEAT.buy_cost:
                    if controller.buy(bot_id, FoodType.MEAT, sx, sy):
                        self.state = M_ON_COUNTER

        #state 3: put meat on counter
        elif self.state == M_ON_COUNTER:
            if self.move_towards(controller, bot_id, cx, cy):
                if controller.place(bot_id, cx, cy):
                    self.state = CHOP_M

        #state 4: chop meat
        elif self.state == CHOP_M:
            if self.move_towards(controller, bot_id, cx, cy):
                if controller.chop(bot_id, cx, cy):
                    self.state = PICK_UP_CHOPPED_M

        #state 5: pickup meat
        elif self.state == PICK_UP_CHOPPED_M:
            if self.move_towards(controller, bot_id, cx, cy):
                if controller.pickup(bot_id, cx, cy):
                    self.state = MEAT_IN_PAN

        #state 6: put meat on counter
        elif self.state == MEAT_IN_PAN:
            if self.move_towards(controller, bot_id, kx, ky):
                # Using the NEW logic where place() starts cooking automatically
                if controller.place(bot_id, kx, ky):
                    self.state = BUY_P

        #state 7: buy the plate
        elif self.state == BUY_P:
            shop_pos = self.find_nearest_tile(controller, bx, by, "SHOP")
            sx, sy = shop_pos
            if self.move_towards(controller, bot_id, sx, sy):
                if controller.get_team_money() >= ShopCosts.PLATE.buy_cost:
                    if controller.buy(bot_id, ShopCosts.PLATE, sx, sy):
                        self.state = P_ON_COUNTER

        #state 8: put the plate on the counter
        elif self.state == P_ON_COUNTER:
            if self.move_towards(controller, bot_id, cx, cy):
                if controller.place(bot_id, cx, cy):
                    self.state = BUY_N

        #state 9: buy noodle
        elif self.state == BUY_N:
            shop_pos = self.find_nearest_tile(controller, bx, by, "SHOP")
            sx, sy = shop_pos
            if self.move_towards(controller, bot_id, sx, sy):
                if controller.get_team_money() >= FoodType.NOODLES.buy_cost:
                    if controller.buy(bot_id, FoodType.NOODLES, sx, sy):
                        self.state = N_TO_P

        #state 10: add noodles to plate
        elif self.state == N_TO_P:
            if self.move_towards(controller, bot_id, cx, cy):
                if controller.add_food_to_plate(bot_id, cx, cy):
                    self.state = WAIT_FOR_M

        #state 11: wait and take meat
        elif self.state == WAIT_FOR_M:
            if self.move_towards(controller, bot_id, kx, ky):
                tile = controller.get_tile(controller.get_team(), kx, ky)
                if tile and isinstance(tile.item, Pan) and tile.item.food:
                    food = tile.item.food
                    if food.cooked_stage == 1:
                        if controller.take_from_pan(bot_id, kx, ky):
                            self.state = M_TO_P
                    elif food.cooked_stage == 2:

                        #trash
                        if controller.take_from_pan(bot_id, kx, ky):
                            self.state = TRASH
                else:
                    if bot_info.get('holding'):
                        #trash
                        self.state = TRASH
                    else:
                        #restart
                        self.state = BUY_M

        #state 12: add meat to plate
        elif self.state == M_TO_P:
            if self.move_towards(controller, bot_id, cx, cy):
                if controller.add_food_to_plate(bot_id, cx, cy):
                    self.state = PICK_UP_COMPLETE_P

        #state 13: pick up the plate
        elif self.state == PICK_UP_COMPLETE_P:
            if self.move_towards(controller, bot_id, cx, cy):
                if controller.pickup(bot_id, cx, cy):
                    self.state = SUBMIT_DISH

        #state 14: submit
        elif self.state == SUBMIT_DISH:
            submit_pos = self.find_nearest_tile(controller, bx, by, "SUBMIT")
            ux, uy = submit_pos
            if self.move_towards(controller, bot_id, ux, uy):
                if controller.submit(bot_id, ux, uy):
                    self.state = INIT

        #state 15: trash
        elif self.state == TRASH:
            trash_pos = self.find_nearest_tile(controller, bx, by, "TRASH")
            if not trash_pos: return
            tx, ty = trash_pos
            if self.move_towards(controller, bot_id, tx, ty):
                if controller.trash(bot_id, tx, ty):
<<<<<<< HEAD
                    self.state = BUY_M #restart


=======
                    self.state = 2 #restart

        # What should we do with additional bots?
>>>>>>> 1d8ed89398682aae1b3fc54baa28fca74deb2843
        for i in range(1, len(my_bots)):
            self.my_bot_id = my_bots[i]
            bot_id = self.my_bot_id

            bot_info = controller.get_bot_state(bot_id)
            bx, by = bot_info['x'], bot_info['y']

            dx = random.choice([-1, 1])
            dy = random.choice([-1, 1])
            nx,ny = bx + dx, by + dy
            if controller.get_map().is_tile_walkable(nx, ny):
                controller.move(bot_id, dx, dy)
                return
