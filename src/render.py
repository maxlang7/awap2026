# render.py
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

import pygame

from game_constants import Team
from game_state import GameState, Order
from tiles import Floor, Wall, Counter, Box, Sink, SinkTable, Cooker, Trash, Submit, Shop
from item import Food, Plate, Pan


# ----------------------------
# Render config
# ----------------------------

@dataclass
class RenderConfig:
    tile_size: int = 32
    gap: int = 24                 # gap between red and blue maps
    hud_height: int = 220         # bottom HUD
    margin: int = 12
    grid_line: int = 1


TILE_COLORS: Dict[str, Tuple[int, int, int]] = {
    "FLOOR": (235, 235, 235),
    "WALL": (60, 60, 60),
    "COUNTER": (190, 155, 110),
    "SINK": (90, 140, 210),
    "SINKTABLE": (100, 200, 210),
    "COOKER": (220, 140, 60),
    "TRASH": (130, 90, 160),
    "SUBMIT": (90, 200, 120),
    "SHOP": (230, 210, 80),
    "BOX": (170, 120, 70),
}

TEAM_COLOR = {
    Team.RED: (220, 60, 60),
    Team.BLUE: (70, 110, 240),
}

TEXT_COLOR = (15, 15, 15)
HUD_BG = (250, 250, 250)
GRID_COLOR = (200, 200, 200)
ITEM_TEXT_COLOR = (20, 20, 20)


def _item_label(it) -> str:
    if it is None:
        return ""
    if isinstance(it, Food):
        # e.g. "MEAT" -> "M"
        return it.food_name[:1]
    if isinstance(it, Plate):
        if it.dirty:
            return "Pd"
        # show up to 3 foods: "P(MTL)"
        letters = "".join([(f.food_name[:1] if isinstance(f, Food) else "?") for f in it.food[:3]])
        return f"P({letters})" if letters else "P"
    if isinstance(it, Pan):
        if it.food is None:
            return "Pan"
        if isinstance(it.food, Food):
            return f"Pan({it.food.food_name[:1]})"
        return "Pan(?)"
    return type(it).__name__[:6]


def _order_label(o: Order, turn: int) -> str:
    req = ",".join([ft.food_name for ft in o.required])
    remaining = o.expires_turn - turn
    return f"#{o.order_id} [{req}]  t={o.created_turn}->{o.expires_turn}  rem={remaining}  R={o.reward} P={o.penalty}"


class Renderer:
    def __init__(self, game_state: GameState, cfg: RenderConfig = RenderConfig()):
        self.gs = game_state
        self.cfg = cfg

        # assume both maps same dimensions
        self.w = self.gs.red_map.width
        self.h = self.gs.red_map.height

        self.map_px_w = self.w * cfg.tile_size
        self.map_px_h = self.h * cfg.tile_size

        self.win_w = cfg.margin * 2 + self.map_px_w * 2 + cfg.gap
        self.win_h = cfg.margin * 2 + self.map_px_h + cfg.hud_height

        self._inited = False
        self._font = None
        self._font_small = None

    def init(self):
        pygame.init()
        pygame.display.set_caption("Competitive Cooking Game")
        self.screen = pygame.display.set_mode((self.win_w, self.win_h))
        self._font = pygame.font.SysFont("Arial", 16)
        self._font_small = pygame.font.SysFont("Arial", 14)
        self.clock = pygame.time.Clock()
        self._inited = True

    def _tile_rect(self, map_left: int, x: int, y: int) -> pygame.Rect:
        # y=0 is bottom in your Map, but pygame y=0 is top => invert
        ts = self.cfg.tile_size
        px = map_left + x * ts
        py = self.cfg.margin + (self.h - 1 - y) * ts
        return pygame.Rect(px, py, ts, ts)

    def _draw_text(self, text: str, x: int, y: int, *, small: bool = False, color=TEXT_COLOR):
        font = self._font_small if small else self._font
        surf = font.render(text, True, color)
        self.screen.blit(surf, (x, y))

    def _draw_map(self, team: Team, map_left: int):
        m = self.gs.get_map(team)

        # tiles
        for x in range(m.width):
            for y in range(m.height):
                t = m.tiles[x][y]
                rect = self._tile_rect(map_left, x, y)
                col = TILE_COLORS.get(getattr(t, "tile_name", "FLOOR"), (220, 220, 220))
                pygame.draw.rect(self.screen, col, rect)

        # grid
        if self.cfg.grid_line > 0:
            for x in range(m.width + 1):
                px = map_left + x * self.cfg.tile_size
                pygame.draw.line(
                    self.screen, GRID_COLOR,
                    (px, self.cfg.margin),
                    (px, self.cfg.margin + self.map_px_h),
                    self.cfg.grid_line
                )
            for y in range(m.height + 1):
                py = self.cfg.margin + y * self.cfg.tile_size
                pygame.draw.line(
                    self.screen, GRID_COLOR,
                    (map_left, py),
                    (map_left + self.map_px_w, py),
                    self.cfg.grid_line
                )

        #items (and box counts)
        for x in range(m.width):
            for y in range(m.height):
                t = m.tiles[x][y]

                if isinstance(t, Box) and getattr(t, "count", 0) > 0:
                    label = _item_label(getattr(t, "item", None))
                    label = f"{label}x{t.count}" if label else f"x{t.count}"
                    rect = self._tile_rect(map_left, x, y)
                    self._draw_text(label, rect.x + 3, rect.y + 3, small=True, color=ITEM_TEXT_COLOR)
                    continue

                it = getattr(t, "item", None)
                if it is None:
                    continue
                label = _item_label(it)
                if not label:
                    continue
                rect = self._tile_rect(map_left, x, y)
                self._draw_text(label, rect.x + 3, rect.y + 3, small=True, color=ITEM_TEXT_COLOR)


        # bots on this team map
        for bot_id, b in self.gs.bots.items():
            if getattr(b, "map_team", b.team) != team:
                continue
            rect = self._tile_rect(map_left, b.x, b.y)
            cx = rect.x + rect.w // 2
            cy = rect.y + rect.h // 2
            pygame.draw.circle(self.screen, TEAM_COLOR[b.team], (cx, cy), rect.w // 3)
            self._draw_text(str(bot_id), rect.x + 2, rect.y + rect.h - 16, small=True, color=(255, 255, 255))


    def _draw_hud(self):
        cfg = self.cfg
        hud_top = cfg.margin + self.map_px_h + cfg.margin
        hud_rect = pygame.Rect(cfg.margin, hud_top, self.win_w - 2 * cfg.margin, cfg.hud_height)
        pygame.draw.rect(self.screen, HUD_BG, hud_rect)

        # header
        self._draw_text(f"Turn: {self.gs.turn}", cfg.margin + 8, hud_top + 8)
        self._draw_text(f"Red money: {self.gs.get_team_money(Team.RED)}", cfg.margin + 140, hud_top + 8, color=TEAM_COLOR[Team.RED])
        self._draw_text(f"Blue money: {self.gs.get_team_money(Team.BLUE)}", cfg.margin + 300, hud_top + 8, color=TEAM_COLOR[Team.BLUE])

        # orders
        left_x = cfg.margin + 8
        right_x = self.win_w // 2 + 8
        y0 = hud_top + 36

        self._draw_text("RED orders (active):", left_x, y0, color=TEAM_COLOR[Team.RED])
        self._draw_text("BLUE orders (active):", right_x, y0, color=TEAM_COLOR[Team.BLUE])

        def active_orders(team: Team) -> List[Order]:
            res = []
            for o in self.gs.orders.get(team, []):
                if o.is_active(self.gs.turn):
                    res.append(o)
            return res

        ro = active_orders(Team.RED)
        bo = active_orders(Team.BLUE)

        yy = y0 + 20
        for o in ro[:6]:
            self._draw_text(_order_label(o, self.gs.turn), left_x, yy, small=True)
            yy += 18

        yy = y0 + 20
        for o in bo[:6]:
            self._draw_text(_order_label(o, self.gs.turn), right_x, yy, small=True)
            yy += 18

        # bots + holding
        bot_y = hud_top + 140
        self._draw_text("Bots:", cfg.margin + 8, bot_y)
        bot_y += 18
        for bot_id, b in sorted(self.gs.bots.items(), key=lambda kv: kv[0]):
            holding = _item_label(b.holding)
            map_team = getattr(b, "map_team", b.team).name
            self._draw_text(
                f"bot {bot_id} [{b.team.name}] on={map_team} pos=({b.x},{b.y}) holding={holding or 'None'}",
                cfg.margin + 8,
                bot_y,
                small=True,
                color=TEAM_COLOR[b.team],
            )
            bot_y += 16

    def render_once(self, *, fps_cap: int = 30) -> bool:
        """
        Draw one frame. Returns False if user closed window.
        """
        if not self._inited:
            self.init()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

        self.screen.fill((245, 245, 245))

        left_red = self.cfg.margin
        left_blue = self.cfg.margin + self.map_px_w + self.cfg.gap

        # titles
        self._draw_text("RED MAP", left_red, 2, color=TEAM_COLOR[Team.RED])
        self._draw_text("BLUE MAP", left_blue, 2, color=TEAM_COLOR[Team.BLUE])

        self._draw_map(Team.RED, left_red)
        self._draw_map(Team.BLUE, left_blue)
        self._draw_hud()

        pygame.display.flip()
        self.clock.tick(fps_cap)
        return True

    def close(self):
        pygame.quit()
