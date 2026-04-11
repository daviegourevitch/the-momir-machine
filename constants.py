from pathlib import Path

SCREEN_WIDTH = 240
SCREEN_HEIGHT = 240
TOP_BANNER_HEIGHT = int(SCREEN_HEIGHT * 0.20)

MANA_VALUES = (
    0,
    0.5,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    1_000_000,
)

STATE_MAIN_MENU = "main_menu"
STATE_SETTINGS_MENU = "settings_menu"
STATE_PRINTER_SETTINGS_MENU = "printer_settings_menu"

ACTION_ROTARY_CW = "rotary_cw"
ACTION_ROTARY_CCW = "rotary_ccw"
ACTION_KNOB_PRESS = "knob_press"
ACTION_UP = "up"
ACTION_DOWN = "down"
ACTION_LEFT = "left"
ACTION_RIGHT = "right"
ACTION_JOY_PRESS = "joy_press"
ACTION_KEY1 = "key1"
ACTION_KEY2 = "key2"
ACTION_KEY3 = "key3"

ALL_HAT_ACTIONS = {
    ACTION_UP,
    ACTION_DOWN,
    ACTION_LEFT,
    ACTION_RIGHT,
    ACTION_JOY_PRESS,
    ACTION_KEY1,
    ACTION_KEY2,
    ACTION_KEY3,
}

ROOT_DIR = Path(__file__).resolve().parent
BELEREN_FONT_PATH = ROOT_DIR / "Beleren-Bold.ttf"
MENU_SCHEMA_PATH = ROOT_DIR / "config" / "menu_schema.json"
SETTINGS_PATH = ROOT_DIR / "config" / "settings.json"
PRINT_SETTINGS_PATH = ROOT_DIR / "config" / "print-settings.json"
CARD_DB_PATH = ROOT_DIR / "data" / "scryfall" / "cards.db"
LISTS_DIR = ROOT_DIR / "lists"
BACKGROUND_PATH = ROOT_DIR / "animation" / "originals" / "from-modo.jpg"
MANA_ICONS_DIR = ROOT_DIR / "mana-icons"
