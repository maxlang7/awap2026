'''item.py File that provides Enums for Food and Food Container Item classes.'''

from abc import ABC
from enum import Enum, auto
from typing import List, Optional, Any
from game_constants import FoodType

class Item(ABC):
    '''Generic Item Class'''
    def __init__(self):
        pass

    def to_dict(self) -> Any:
        '''dictionary serialization for purposes of JSON'''
        return {"type": type(self).__name__}


class Food(Item):
    def __init__(self, food_type: FoodType):
        self.food_name = food_type.food_name
        self.food_id = food_type.food_id
        self.can_chop = food_type.can_chop
        self.can_cook = food_type.can_cook
        self.buy_cost = food_type.buy_cost

        self.chopped = False
        self.cooked_stage = 0 #0 is raw, 1 is cooked, 2 is burnt

    def to_dict(self):
        return {
            "type": "Food",
            "food_name": self.food_name,
            "food_id": self.food_id,
            "chopped": self.chopped,
            "cooked_stage": self.cooked_stage,
        }

class Plate(Item):
    def __init__(self, food: List[Item] = [], dirty: bool = False):
        self.food = food if food is not None else [] #what food is on the plate, can have multiple foods on the plate
        self.dirty = dirty #if the plate is dirty, no food should be on it

    def to_dict(self):
        return {
            "type": "Plate",
            "dirty": self.dirty,
            #serialize each food item on the plate
            "food": [f.to_dict() for f in self.food], 
        }

class Pan(Item):
    def __init__(self, food: Optional[Food] = None):
        self.food = food #what food is on the pan, only 1 food at at a time on the pan

    def to_dict(self):
        return {
            "type": "Pan",
            "food": self.food.to_dict() if self.food else None
        }