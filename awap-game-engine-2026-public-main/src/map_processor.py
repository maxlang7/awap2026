# map_processor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import copy

from game_constants import Team, FoodType, GameConstants
from map import Map
from tiles import Tile, Floor, Wall, Counter, Sink, SinkTable, Cooker, Trash, Submit, Shop, Box
from game_state import Order


# ----------------------------
# Legend with parsing configurations
# ----------------------------

CHAR_TO_TILE: Dict[str, type] = {
    '.': Floor,
    '#': Wall,
    'C': Counter,
    'K': Cooker,
    'S': Sink,
    'T': SinkTable,
    'R': Trash,
    'U': Submit, 
    '$': Shop,
    'B': Box,
}

BOT_SPAWN_CHARS = {'b'}


@dataclass
class ParsedMap:
    map_obj: Map
    spawns_red: List[Tuple[int, int]]
    spawns_blue: List[Tuple[int, int]]
    orders: List[Order]

    switch_turn: int
    switch_duration: int


def parse_switch_line(line: str, default_turn: int, default_duration: int) -> Tuple[int, int]:
    '''
    Accepts in format: SWITCH: turn=250 duration=100
    '''

    #no switch prefix
    rest = line.split(":", 1)[1].strip() if ":" in line else ""
    if not rest:
        return default_turn, default_duration

    tokens = rest.split()
    kv: Dict[str, str] = {}
    for tok in tokens:
        if '=' not in tok:
            continue
        k, v = tok.split('=', 1)
        kv[k.strip().lower()] = v.strip()

    turn = int(kv.get("turn", default_turn))
    duration = int(kv.get("duration", default_duration))
    return turn, duration


def extract_optional_switch_config(lines: List[str]) -> Tuple[List[str], int, int]:
    '''
    remove the switch line so it doesn't get added to the map rows
    '''
    switch_turn = GameConstants.MIDGAME_SWITCH_TURN
    switch_duration = GameConstants.MIDGAME_SWITCH_DURATION

    kept: List[str] = []
    for ln in lines:
        s = ln.strip()
        up = s.upper()
        if up.startswith("SWITCH:"):
            switch_turn, switch_duration = parse_switch_line(
                s,
                default_turn=switch_turn,
                default_duration=switch_duration,
            )
            continue
        kept.append(ln)
    return kept, switch_turn, switch_duration


def clone_tiles_grid(tiles: List[List[Tile]]) -> List[List[Tile]]:
    return copy.deepcopy(tiles)


def read_nonempty_noncomment_lines(raw_lines: List[str]) -> List[str]:
    '''CSV helper'''

    out: List[str] = []

    for ln in raw_lines:
        s = ln.rstrip('\n')

        if not s.strip():
            continue

        #for comments just in case
        if s.lstrip().startswith('//'):
            continue

        out.append(s.rstrip())
        
    return out


def split_layout_and_orders(lines: List[str]) -> Tuple[List[str], List[str]]:
    '''
    map layout
    orders

    is the map processing script
    '''
    idx = None
    for i, ln in enumerate(lines):
        if ln.strip().upper() == 'ORDERS:':
            idx = i
            break

    if idx is None:
        return lines, []

    layout = lines[:idx]
    orders = lines[idx + 1 :]
    return layout, orders


def parse_required_csv(s: str) -> List[FoodType]:
    '''
    parsing the CVS
    '''

    parts = [p.strip() for p in s.split(',') if p.strip()]
    req: List[FoodType] = []

    for p in parts:

        # allow FoodType.BUNS or BUNS either work
        name = p.split('.', 1)[-1].upper()
        try:
            req.append(FoodType[name])
        except KeyError as e:
            raise ValueError(f'Unknown FoodType "{p}" (parsed as "{name}")') from e
        
    return req


def parse_order_line(line: str, *, next_order_id: int, default_reward: int, default_penalty: int) -> Tuple[Order, int]:
    '''
    allow comments
    '''
    # strip inline comments (safe here; not safe in map layout because '#' are walls)
    line = line.split('//', 1)[0].split('#', 1)[0].strip()
    if not line:
        return None, next_order_id  # type: ignore

    tokens = line.split()
    kv: Dict[str, str] = {}
    for tok in tokens:
        if '=' not in tok:
            raise ValueError(f'Bad order token "{tok}". Expected key=value.')
        k, v = tok.split('=', 1)
        kv[k.strip().lower()] = v.strip()

    if 'start' not in kv or 'duration' not in kv or 'required' not in kv:
        raise ValueError(f'Order line missing fields. Need start= duration= required=. Got: {line}')

    start = int(kv['start'])
    duration = int(kv['duration'])
    reward = int(kv.get('reward', default_reward))
    penalty = int(kv.get('penalty', default_penalty))
    required = parse_required_csv(kv['required'])

    order = Order(
        order_id=next_order_id,
        required=required,
        created_turn=start,
        expires_turn=start + duration,
        reward=reward,
        penalty=penalty,
    )

    return order, next_order_id + 1


def load_map_from_txt(
    path: str,
    *,
    team: Team = Team.RED,
    legend: Optional[Dict[str, type]] = None,
    default_reward: int = 5,
    default_penalty: int = 2,
) -> ParsedMap:
    '''
    loads both map layout and orders section, returns a ParsedMap() obj
    '''
    if legend is None:
        legend = CHAR_TO_TILE

    with open(path, 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()

    lines = read_nonempty_noncomment_lines(raw_lines)
    lines, switch_turn, switch_duration = extract_optional_switch_config(lines)
    layout_lines, order_lines = split_layout_and_orders(lines)

    if not layout_lines:
        raise ValueError(f'{path}: no map rows found')

    width = len(layout_lines[0])
    if any(len(r) != width for r in layout_lines):
        bad = [i for i, r in enumerate(layout_lines) if len(r) != width]
        raise ValueError(f'{path}: inconsistent row widths in layout; bad row indices={bad}')

    height = len(layout_lines)

    tiles: List[List[Tile]] = [[Floor() for _ in range(height)] for _ in range(width)]
    spawns_red: List[Tuple[int, int]] = []
    spawns_blue: List[Tuple[int, int]] = []

    for file_row, row in enumerate(layout_lines):
        y = height - 1 - file_row
        for x, ch in enumerate(row):
            if ch in BOT_SPAWN_CHARS:
                spawns_red.append((x, y))
                spawns_blue.append((x, y))
                tiles[x][y] = Floor()
                continue

            tile_cls = legend.get(ch)
            if tile_cls is None:
                raise ValueError(f'{path}: unknown tile char "{ch}" at (x={x}, file_row={file_row})')
            tiles[x][y] = tile_cls()

    #parsing then clone the orders later for both maps
    orders: List[Order] = []
    next_order_id = 1
    for ln in order_lines:
        parsed, next_order_id = parse_order_line(
            ln,
            next_order_id=next_order_id,
            default_reward=default_reward,
            default_penalty=default_penalty,
        )
        if parsed is not None:
            orders.append(parsed)

    m = Map(width=width, height=height, tiles=tiles, team=team, orders=[])  # Map.orders is unused in your GameState
    return ParsedMap(map_obj=m, spawns_red=spawns_red, spawns_blue=spawns_blue, orders=orders, switch_turn=switch_turn, switch_duration=switch_duration)


def load_two_team_maps_and_orders(path: str, default_reward: int = 5, default_penalty: int = 2) -> Tuple[Map, Map, List[Order], List[Order], ParsedMap]:
    '''
    returns
      (map_red, map_blue, orders_red, orders_blue, parsed)

    different map, orders objects
    '''
    parsed = load_map_from_txt(
        path,
        team=Team.RED,
        default_reward=default_reward,
        default_penalty=default_penalty,
    )

    map_red = parsed.map_obj
    map_blue = Map(
        width=map_red.width,
        height=map_red.height,
        tiles=clone_tiles_grid(map_red.tiles),
        team=Team.BLUE,
        orders=[],
    )

    orders_red = parsed.orders
    orders_blue = copy.deepcopy(parsed.orders)

    return map_red, map_blue, orders_red, orders_blue, parsed
