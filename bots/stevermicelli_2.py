import random
from collections import deque
from typing import Tuple, Optional, List


import sys
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
        self.current_order = None
    # ===== STATE EXECUTION METHODS =====

    def do_init(self, controller: RobotController, bot_id: int, kx: int, ky: int):
        """State 0: init + checking the pan"""
        tile = controller.get_tile(controller.get_team(), kx, ky)
        if tile and isinstance(tile.item, Pan):
            self.state = BUY_M
        else:
            self.state = BUY_PAN

    def do_buy_pan(self, controller: RobotController, bot_id: int,
                    bot_info: dict, bx: int, by: int, kx: int, ky: int):
        """State 1: buy pan"""
        holding = bot_info.get('holding')
        if holding:  # assume it's the pan
            if self.move_towards(controller, bot_id, kx, ky):
                if controller.place(bot_id, kx, ky):
                    self.state = BUY_M
        else:
            shop_pos = self.find_nearest_tile(controller, bx, by, "SHOP")
            if not shop_pos:
                return
            sx, sy = shop_pos
            if self.move_towards(controller, bot_id, sx, sy):
                if controller.get_team_money(controller.get_team()) >= ShopCosts.PAN.buy_cost:
                    controller.buy(bot_id, ShopCosts.PAN, sx, sy)

    def do_buy_meat(self, controller: RobotController, bot_id: int,
                     bx: int, by: int):
        """State 2: buy meat"""
        shop_pos = self.find_nearest_tile(controller, bx, by, "SHOP")
        sx, sy = shop_pos
        if self.move_towards(controller, bot_id, sx, sy):
            if controller.get_team_money(controller.get_team()) >= FoodType.MEAT.buy_cost:
                if controller.buy(bot_id, FoodType.MEAT, sx, sy):
                    self.state = M_ON_COUNTER

    def do_place_meat(self, controller: RobotController, bot_id: int,
                       cx: int, cy: int):
        """State 3: put meat on counter"""
        if self.move_towards(controller, bot_id, cx, cy):
            if controller.place(bot_id, cx, cy):
                self.state = CHOP_M

    def do_chop_meat(self, controller: RobotController, bot_id: int,
                      cx: int, cy: int):
        """State 4: chop meat"""
        if self.move_towards(controller, bot_id, cx, cy):
            if controller.chop(bot_id, cx, cy):
                self.state = PICK_UP_CHOPPED_M

    def do_pickup_meat(self, controller: RobotController, bot_id: int,
                        cx: int, cy: int):
        """State 5: pickup meat"""
        if self.move_towards(controller, bot_id, cx, cy):
            if controller.pickup(bot_id, cx, cy):
                self.state = MEAT_IN_PAN

    def do_meat_to_pan(self, controller: RobotController, bot_id: int,
                        kx: int, ky: int):
        """State 6: put meat in pan"""
        if self.move_towards(controller, bot_id, kx, ky):
            # Using the NEW logic where place() starts cooking automatically
            if controller.place(bot_id, kx, ky):
                self.state = BUY_P

    def do_buy_plate(self, controller: RobotController, bot_id: int,
                      bx: int, by: int):
        """State 7: buy the plate"""
        shop_pos = self.find_nearest_tile(controller, bx, by, "SHOP")
        sx, sy = shop_pos
        if self.move_towards(controller, bot_id, sx, sy):
            if controller.get_team_money(controller.get_team()) >= ShopCosts.PLATE.buy_cost:
                if controller.buy(bot_id, ShopCosts.PLATE, sx, sy):
                    self.state = P_ON_COUNTER

    def do_place_plate(self, controller: RobotController, bot_id: int,
                        cx: int, cy: int):
        """State 8: put the plate on the counter"""
        if self.move_towards(controller, bot_id, cx, cy):
            if controller.place(bot_id, cx, cy):
                self.state = BUY_N

    def do_buy_noodles(self, controller: RobotController, bot_id: int,
                        bx: int, by: int):
        """State 9: buy noodle"""
        shop_pos = self.find_nearest_tile(controller, bx, by, "SHOP")
        sx, sy = shop_pos
        if self.move_towards(controller, bot_id, sx, sy):
            if controller.get_team_money(controller.get_team()) >= FoodType.NOODLES.buy_cost:
                if controller.buy(bot_id, FoodType.NOODLES, sx, sy):
                    self.state = N_TO_P

    def do_noodles_to_plate(self, controller: RobotController, bot_id: int,
                             cx: int, cy: int):
        """State 10: add noodles to plate"""
        if self.move_towards(controller, bot_id, cx, cy):
            if controller.add_food_to_plate(bot_id, cx, cy):
                self.state = WAIT_FOR_M

    def do_wait_meat(self, controller: RobotController, bot_id: int,
                      bot_info: dict, kx: int, ky: int):
        """State 11: wait and take meat"""
        if self.move_towards(controller, bot_id, kx, ky):
            tile = controller.get_tile(controller.get_team(), kx, ky)
            if tile and isinstance(tile.item, Pan) and tile.item.food:
                food = tile.item.food
                if food.cooked_stage == 1:
                    if controller.take_from_pan(bot_id, kx, ky):
                        self.state = M_TO_P
                elif food.cooked_stage == 2:
                    # trash
                    if controller.take_from_pan(bot_id, kx, ky):
                        self.state = TRASH
            else:
                if bot_info.get('holding'):
                    # trash
                    self.state = TRASH
                else:
                    # restart
                    self.state = BUY_M

    def do_meat_to_plate(self, controller: RobotController, bot_id: int,
                          cx: int, cy: int):
        """State 12: add meat to plate"""
        if self.move_towards(controller, bot_id, cx, cy):
            if controller.add_food_to_plate(bot_id, cx, cy):
                self.state = PICK_UP_COMPLETE_P

    def do_pickup_plate(self, controller: RobotController, bot_id: int,
                         cx: int, cy: int):
        """State 13: pick up the plate"""
        if self.move_towards(controller, bot_id, cx, cy):
            if controller.pickup(bot_id, cx, cy):
                self.state = SUBMIT_DISH

    def do_submit(self, controller: RobotController, bot_id: int,
                   bx: int, by: int):
        """State 14: submit"""
        submit_pos = self.find_nearest_tile(controller, bx, by, "SUBMIT")
        ux, uy = submit_pos
        if self.move_towards(controller, bot_id, ux, uy):
            if controller.submit(bot_id, ux, uy):
                self.state = INIT

    def do_trash(self, controller: RobotController, bot_id: int,
                  bx: int, by: int):
        """State 15: trash"""
        trash_pos = self.find_nearest_tile(controller, bx, by, "TRASH")
        if not trash_pos:
            return
        tx, ty = trash_pos
        if self.move_towards(controller, bot_id, tx, ty):
            if controller.trash(bot_id, tx, ty):
                self.state = BUY_M  # restart

    # ===== UTILITY METHODS =====

    def get_bfs_path(self, controller: RobotController, start: Tuple[int, int],
                     target_predicate) -> Optional[Tuple[int, int]]:
        queue = deque([(start, [])])
        visited = set([start])
        w, h = self.map.width, self.map.height

        while queue:
            (curr_x, curr_y), path = queue.popleft()
            tile = controller.get_tile(controller.get_team(), curr_x, curr_y)
            if target_predicate(curr_x, curr_y, tile):
                if not path:
                    return (0, 0)
                return path[0]

            for dx in [0, -1, 1]:
                for dy in [0, -1, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = curr_x + dx, curr_y + dy
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                        if controller.get_map(controller.get_team()).is_tile_walkable(nx, ny):
                            visited.add((nx, ny))
                            queue.append(((nx, ny), path + [(dx, dy)]))
        return None

    def move_towards(self, controller: RobotController, bot_id: int,
                    target_x: int, target_y: int) -> bool:
        bot_state = controller.get_bot_state(bot_id)
        bx, by = bot_state['x'], bot_state['y']

        def is_adjacent_to_target(x, y, tile):
            return max(abs(x - target_x), abs(y - target_y)) <= 1

        if is_adjacent_to_target(bx, by, None):
            return True

        step = self.get_bfs_path(controller, (bx, by), is_adjacent_to_target)
        if step and (step[0] != 0 or step[1] != 0):
            controller.move(bot_id, step[0], step[1])
            return False

        return False

    def find_nearest_tile(self, controller: RobotController, bot_x: int, bot_y: int,
                         tile_name: str) -> Optional[Tuple[int, int]]:
        best_dist = 9999
        best_pos = None
        m = controller.get_map(controller.get_team())
        for x in range(m.width):
            for y in range(m.height):
                tile = m.tiles[x][y]
                if tile.tile_name == tile_name:
                    dist = max(abs(bot_x - x), abs(bot_y - y))
                    if dist < best_dist:
                        best_dist = dist
                        best_pos = (x, y)
        return best_pos


    def get_first_priority_order(self, orders):
        # Reorders the list of dictionaries inside orders to priorize which ones to work in what order
        #for order in orders:
            return None
    def play_turn(self, controller: RobotController):
        team=controller.get_team()
        # For testing
        time.sleep(0.1)
        my_bots = controller.get_team_bot_ids(team)
        if not my_bots:
            return
            
        if self.current_order == None:
            orders = controller.get_orders(team)
            self.current_order = get_first_priority_order(orders)

        # Bot 1
        self.my_bot_id = my_bots[0]
        bot_id = self.my_bot_id

        bot_info = controller.get_bot_state(bot_id)
        bx, by = bot_info['x'], bot_info['y']

        if self.assembly_counter is None:
            self.assembly_counter = self.find_nearest_tile(controller, bx, by, "COUNTER")
        if self.cooker_loc is None:
            self.cooker_loc = self.find_nearest_tile(controller, bx, by, "COOKER")

        if not self.assembly_counter or not self.cooker_loc:
            return

        cx, cy = self.assembly_counter
        kx, ky = self.cooker_loc

        if self.state in [BUY_M, BUY_P, BUY_N] and bot_info.get('holding'):
            self.state = TRASH

        # State 0: init + checking the pan
        if self.state == INIT:
            self.do_init(controller, bot_id, kx, ky)

        # State 1: buy pan
        elif self.state == BUY_PAN:
            self.do_buy_pan(controller, bot_id, bot_info, bx, by, kx, ky)

        # State 2: buy meat
        elif self.state == BUY_M:
            self.do_buy_meat(controller, bot_id, bx, by)

        # State 3: put meat on counter
        elif self.state == M_ON_COUNTER:
            self.do_place_meat(controller, bot_id, cx, cy)

        # State 4: chop meat
        elif self.state == CHOP_M:
            self.do_chop_meat(controller, bot_id, cx, cy)

        # State 5: pickup meat
        elif self.state == PICK_UP_CHOPPED_M:
            self.do_pickup_meat(controller, bot_id, cx, cy)

        # State 6: put meat in pan
        elif self.state == MEAT_IN_PAN:
            self.do_meat_to_pan(controller, bot_id, kx, ky)

        # State 7: buy the plate
        elif self.state == BUY_P:
            self.do_buy_plate(controller, bot_id, bx, by)

        # State 8: put the plate on the counter
        elif self.state == P_ON_COUNTER:
            self.do_place_plate(controller, bot_id, cx, cy)

        # State 9: buy noodle
        elif self.state == BUY_N:
            self.do_buy_noodles(controller, bot_id, bx, by)

        # State 10: add noodles to plate
        elif self.state == N_TO_P:
            self.do_noodles_to_plate(controller, bot_id, cx, cy)

        # State 11: wait and take meat
        elif self.state == WAIT_FOR_M:
            self.do_wait_meat(controller, bot_id, bot_info, kx, ky)

        # State 12: add meat to plate
        elif self.state == M_TO_P:
            self.do_meat_to_plate(controller, bot_id, cx, cy)

        # State 13: pick up the plate
        elif self.state == PICK_UP_COMPLETE_P:
            self.do_pickup_plate(controller, bot_id, cx, cy)

        # State 14: submit
        elif self.state == SUBMIT_DISH:
            self.do_submit(controller, bot_id, bx, by)

        # State 15: trash
        elif self.state == TRASH:
            self.do_trash(controller, bot_id, bx, by)

        #------------------------
        # BOT 2 ACTIONS

        self.my_bot_id = my_bots[1]
        bot_id = self.my_bot_id

        bot_info = controller.get_bot_state(bot_id)
        bx, by = bot_info['x'], bot_info['y']

        dy = 0
        if controller.get_turn() % 2 == 0:
            dx = 1
        else:
            dx = -1

        nx, ny = bx + dx, by + dy
        if controller.get_map(controller.get_team()).is_tile_walkable(nx, ny):
            controller.move(bot_id, dx, dy)
            return
