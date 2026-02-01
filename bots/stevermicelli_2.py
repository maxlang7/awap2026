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

        self.bot_1_tasks = None
        self.bot_2_tasks = None
        self.bot_1_current_task = None
        self.bot_2_current_task = None

        self.counter_x, self.counter_y = self.find_nearest_tile(self.map, 0, 0, "COUNTER")
        # Base location where we find everything else from
        x,y=self.counter_x,self.counter_y

        self.cooker_x, self.cooker_y = self.find_nearest_tile(self.map, x, y, "COOKER")
        self.submit_x, self.submit_y = self.find_nearest_tile(self.map, x, y, "SUBMIT")
        self.shop_x, self.shop_y = self.find_nearest_tile(self.map, x, y, "SHOP")
        self.box_x, self.box_y = self.find_nearest_tile(self.map, x, y, "BOX")





         # ===== INITIALIZATION =====

    def do_init(self, controller: RobotController, bot_id: int, kx: int, ky: int):
        """State 0: init + checking the pan"""
        tile = controller.get_tile(controller.get_team(), kx, ky)
        if tile and isinstance(tile.item, Pan):
            self.state = BUY_M
        else:
            self.state = BUY_PAN

    # ===== KITCHEN SETUP PHASE =====

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

    # ===== MEAT PREPARATION PHASE =====

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

    # ===== COOKING PHASE =====

    def do_meat_to_pan(self, controller: RobotController, bot_id: int,
                        kx: int, ky: int):
        """State 6: put meat in pan"""
        if self.move_towards(controller, bot_id, kx, ky):
            # Using the NEW logic where place() starts cooking automatically
            if controller.place(bot_id, kx, ky):
                self.state = BUY_P

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

    # ===== PLATE PREPARATION PHASE =====

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

    # ===== DISH ASSEMBLY PHASE =====

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

    # ===== COMPLETION & ERROR HANDLING =====

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

    def find_nearest_tile(self, map, bot_x: int, bot_y: int,
                         tile_name: str) -> Optional[Tuple[int, int]]:
        best_dist = 9999
        best_pos = None
        m = map
        for x in range(m.width):
            for y in range(m.height):
                tile = m.tiles[x][y]
                if tile.tile_name == tile_name:
                    dist = max(abs(bot_x - x), abs(bot_y - y))
                    if dist < best_dist:
                        best_dist = dist
                        best_pos = (x, y)
        return best_pos

    # def get_ingredients_cost(self, ingredients):
    #     cost=0
    #     num_cooked = 0
    #     num_chopped = 0
    #     num_cooked_and_chopped = 0
    #     for ingredient in ingredients:
    #         if ingredient == "ONION":
    #             cost+=30
    #             num_chopped+=1
    #         elif ingredient == "EGG":
    #             cost+=20
    #             num_cooked+=1
    #         elif ingredient == "MEAT":
    #             cost+=80
    #             num_cooked_and_chopped+=1
    #         elif ingredient == "NOODLES":
    #             cost+=40
    #         elif ingredient == "SAUCE":
    #             cost+=10
    #     return cost, num_cooked, num_chopped, num_cooked_and_chopped


    # def get_expected_value(self, order):
    #     ingredient_cost = self.get_ingredients_cost(order['required'])
    #     total_time = time_to_chop+time_to_cook+time_for_meat+
    #     return ingredient_cost, total_time

    # def prioritize_orders(self, orders):
    #     for order in orders:
    #         order['expected_value'] = self.get_expected_value(order)

    def do_first_bot_turn(self, controller):
        bot_id=controller.get_team_bot_ids(controller.get_team())[0]
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

    def do_second_bot_turn(self, controller):
        bot_id=controller.get_team_bot_ids(controller.get_team())[1]
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

        dy = 0
        if controller.get_turn() % 2 == 0:
            dx = 1
        else:
            dx = -1

        nx, ny = bx + dx, by + dy
        if controller.get_map(controller.get_team()).is_tile_walkable(nx, ny):
            controller.move(bot_id, dx, dy)
            return

    def get_tasks(self,orders):
        bot_1_tasks=[]
        bot_2_tasks=[]
        onion_1_tasks=["go_store", "buy_onion", "go_counter", "place_counter", "chop"]
        meat_1_tasks=["go_store", "buy_meat", "go_counter", "place_counter", "chop", "pickup_counter", "go_cooker", "cook", "go_store"]
        egg_1_tasks=["go_store", "buy_egg", "go_cooker", "cook"]

        move_2_tasks = ["go_box", "go_box", "place_box", "place_box"]
        onion_2_tasks=["go_counter", "pickup_counter"] + move_2_tasks
        meat_2_tasks=["go_cooker", "go_cooker", "pickup_cooker"] + move_2_tasks
        egg_2_tasks=meat_2_tasks

        noodles_2_tasks = ["go_store", "buy_noodles", "go_box", "place_box"]
        sauce_2_tasks = ["go_store", "buy_sauce", "go_box", "place_box"]

        submit_2_tasks = ["go_store", "buy_plate", "go_box"]
        for order in orders:
            onion_count=order['required'].count("ONION")
            meat_count=order['required'].count("MEAT")
            egg_count=order['required'].count("EGG")
            noodles_count=order['required'].count("NOODLES")
            sauce_count =order['required'].count("SAUCE")
            total_ingredients = meat_count+egg_count+noodles_count+sauce_count+onion_count

            for _ in range(onion_count):
                bot_1_tasks+=onion_1_tasks
                bot_2_tasks+=onion_2_tasks
            for _ in range(meat_count):
                bot_1_tasks+=meat_1_tasks
                bot_2_tasks+=meat_2_tasks
            for _ in range(egg_count):
                bot_1_tasks+=egg_1_tasks
                bot_2_tasks+=egg_2_tasks
            for _ in range(noodles_count):
                bot_2_tasks+=noodles_2_tasks
            for _ in range(sauce_count):
                bot_2_tasks+=sauce_2_tasks
            bot_2_tasks += submit_2_tasks + ["pickup_box"]*(total_ingredients) + ["go_submit"] + ["place_submit"]

        return self.reorder_tasks(bot_1_tasks, bot_2_tasks)

    def reorder_tasks(tasks1,tasks2):
        
    def play_turn(self, controller: RobotController):
        # For testing
        #time.sleep(0.1)
       # print(f"Bot 1 tasks: {self.bot_1_tasks}")
        print(f"Bot 2 tasks: {self.bot_2_tasks}")

        #print(self.bot_1_current_task)

        team = controller.get_team()

        bot_1_id = controller.get_team_bot_ids(team)[0]
        bot_2_id = controller.get_team_bot_ids(team)[1]

        orders = controller.get_orders(team)
        # Prioritize Orders???

        # Get Tasks for both bots
        if self.bot_1_tasks is None and self.bot_2_tasks is None:
            bot_1_order_tasks, bot_2_order_tasks = self.get_tasks(orders)
            init_tasks = [] #["go_store", "buy_pan", "go_cooker", "place_cooker"]
            self.bot_1_tasks = init_tasks + bot_1_order_tasks
            self.bot_2_tasks = init_tasks + bot_2_order_tasks

        # BOT 1 LOGIC
        if self.bot_1_tasks:
            if self.bot_1_current_task is None:
                self.bot_1_current_task = self.bot_1_tasks[0]

            task = self.bot_1_current_task
            task_done = False
            if task == "go_store":
                if self.move_towards(controller, bot_1_id, self.shop_x, self.shop_y):
                    task_done = True
            elif task == "go_cooker":
                if self.move_towards(controller, bot_1_id, self.cooker_x, self.cooker_y):
                    task_done = True
            elif task == "go_counter":
                if self.move_towards(controller, bot_1_id, self.counter_x, self.counter_y):
                    task_done = True
            elif task == "buy_onion":
                if controller.buy(bot_1_id, FoodType.ONION, self.shop_x, self.shop_y):
                    task_done = True
            elif task == "buy_meat":
                if controller.buy(bot_1_id, FoodType.MEAT, self.shop_x, self.shop_y):
                    task_done = True
            elif task == "buy_egg":
                if controller.buy(bot_1_id, FoodType.EGG, self.shop_x, self.shop_y):
                    task_done = True
            elif task == "buy_pan":
                if controller.buy(bot_1_id, ShopCosts.PAN, self.shop_x, self.shop_y):
                    task_done = True
            elif task == "chop":
                if controller.chop(bot_1_id, self.counter_x, self.counter_y):
                    task_done = True
            elif task == "cook":
                if controller.place(bot_1_id, self.cooker_x, self.cooker_y):
                    task_done = True
            elif task == "place_counter":
                if controller.place(bot_1_id, self.counter_x, self.counter_y):
                    task_done = True
            elif task == "place_box":
                if controller.place(bot_1_id, self.box_x, self.box_y):
                    task_done = True
            elif task == "pickup_counter":
                if controller.pickup(bot_1_id, self.counter_x, self.counter_y):
                    task_done = True
            elif task == "pickup_cooker":
                if controller.pickup(bot_1_id, self.cooker_x, self.cooker_y):
                    task_done = True

            if task_done:
                self.bot_1_tasks.pop(0)
                self.bot_1_current_task = None

        # BOT 2 LOGIC
        if self.bot_2_tasks:
            if self.bot_2_current_task is None:
                popped=self.bot_2_tasks.pop(0)
                print(popped)
                self.bot_2_current_task = self.bot_2_tasks[0]

            task = self.bot_2_current_task
            #print(task)
            task_done = False
            if task == "go_store":
                if self.move_towards(controller, bot_2_id, self.shop_x, self.shop_y):
                    print(f"Did task:{task}")
                    task_done = True
            elif task == "go_cooker":
                print("go_cooker!!")
                if self.move_towards(controller, bot_2_id, self.cooker_x, self.cooker_y):
                    print(f"Did task:{task}")
                    task_done = True
            elif task == "go_submit":
                if self.move_towards(controller, bot_2_id, self.submit_x, self.submit_y):
                    print(f"Did task:{task}")
                    task_done = True
            elif task == "submit":
                if controller.place(bot_2_id, self.submit_x, self.submit_y):
                    print(f"Did task:{task}")
                    task_done = True
            elif task == "go_counter":
                if self.move_towards(controller, bot_2_id, self.counter_x, self.counter_y):
                    print(f"Did task:{task}")
                    task_done = True
            elif task == "go_box":
                if self.move_towards(controller, bot_2_id, self.box_x, self.box_y):
                    print(f"Did task:{task}")
                    task_done = True
            elif task == "place_box":
                if controller.place(bot_2_id, self.box_x, self.box_y):
                    print(f"Did task:{task}")
                    task_done = True
            elif task == "pickup_box":
                if controller.pickup(bot_2_id, self.box_x, self.box_y):
                    print(f"Did task:{task}")
                    task_done = True
            elif task == "pickup_counter":
                if controller.pickup(bot_2_id, self.counter_x, self.counter_y):
                    print(f"Did task:{task}")
                    task_done = True
            #print(task)
            elif task == "pickup_cooker":
                tile = controller.get_tile(team, self.cooker_x, self.cooker_y)
                if tile and isinstance(tile.item, Pan) and tile.item.food and tile.item.food.cooked_stage == 1:
                    print("DEBUG: Meat is cooked, trying to take from pan.")
                    if controller.take_from_pan(bot_2_id, self.cooker_x, self.cooker_y):
                        task_done = True


            if task_done:
                print("task done")
                self.bot_2_tasks.pop(0)
                self.bot_2_current_task = None

        if not self.bot_1_tasks and not self.bot_2_tasks:
            print("Nothing to do")
