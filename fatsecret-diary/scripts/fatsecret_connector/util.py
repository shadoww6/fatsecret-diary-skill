"""Parsing helpers, output formatting and food lookup across your own history."""

from __future__ import annotations

import csv
import re
import sys
from datetime import date, datetime, timedelta

from .config import DATA_DIR

MEALS = ["breakfast", "lunch", "dinner", "other"]
MEAL_ALIASES = {
    # English
    "breakfast": "breakfast", "b": "breakfast", "lunch": "lunch", "l": "lunch",
    "dinner": "dinner", "d": "dinner", "supper": "dinner",
    "other": "other", "snack": "other", "snacks": "other", "s": "other",
    # Russian
    "завтрак": "breakfast", "обед": "lunch", "ужин": "dinner", "перекус": "other", "другое": "other",
    # Chinese
    "早餐": "breakfast", "早饭": "breakfast", "午餐": "lunch", "午饭": "lunch",
    "晚餐": "dinner", "晚饭": "dinner", "零食": "other", "加餐": "other", "其他": "other",
}
MEAL_NAMES = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "other": "Snacks/Other"}
NAMED_DAYS = {
    "today": 0, "yesterday": -1, "tomorrow": 1,
    "сегодня": 0, "вчера": -1, "позавчера": -2, "завтра": 1,
    "今天": 0, "昨天": -1, "前天": -2, "明天": 1,
}


class UserError(Exception):
    pass


# --- parsing ----------------------------------------------------------------

def parse_date(s) -> date:
    """today / yesterday / -N / YYYY-MM-DD / DD.MM / DD.MM.YYYY (plus Russian and Chinese day names)"""
    if s is None or isinstance(s, date):
        return s or date.today()
    t = s.strip().lower()
    today = date.today()
    if t in NAMED_DAYS:
        return today + timedelta(days=NAMED_DAYS[t])
    if re.fullmatch(r"[+-]\d{1,4}", t):
        return today + timedelta(days=int(t))
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", t)
    if m:
        d = date(today.year, int(m.group(2)), int(m.group(1)))
        return d if d <= today + timedelta(days=1) else d.replace(year=today.year - 1)
    raise UserError(f"can't parse date '{s}'. Examples: 2026-10-03, 03.10, yesterday, -2")


def parse_meal(s, default_by_time=False):
    if s is None:
        if not default_by_time:
            return None
        h = datetime.now().hour
        return "breakfast" if h < 11 else "lunch" if h < 16 else "dinner" if h < 21 else "other"
    meal = MEAL_ALIASES.get(s.strip().lower())
    if not meal:
        raise UserError(f"unknown meal '{s}'. Use: breakfast, lunch, dinner, other")
    return meal


def parse_number(s):
    try:
        return float(str(s).replace(",", "."))
    except ValueError:
        return None


def split_query_amount(words):
    """['milk', 'parmalat', '1,5'] -> ('milk parmalat', 1.5). Amount is optional."""
    words = list(words)
    amount = None
    if len(words) > 1 and parse_number(words[-1]) is not None:
        amount = parse_number(words.pop())
    return " ".join(words), amount


# --- formatting ---------------------------------------------------------------

def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def fmt_num(x, digits=1):
    x = num(x)
    s = f"{x:.{digits}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def macro_line(d):
    return (f"{fmt_num(d.get('calories'), 0):>5} kcal  P {fmt_num(d.get('protein')):>5}  "
            f"F {fmt_num(d.get('fat')):>5}  C {fmt_num(d.get('carbohydrate')):>5}")


def print_table(rows, headers):
    rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))


def norm(s):
    return (s or "").lower().replace("ё", "е").replace(",", ".")


def matches(query, text):
    text = norm(text)
    return all(w in text for w in norm(query).split())


def choose(options, describe, pick=None, what="option"):
    """Pick one of several options: by --pick N, interactively, or fail with the list."""
    if not options:
        return None
    if pick is not None:
        if not 1 <= pick <= len(options):
            raise UserError(f"--pick must be between 1 and {len(options)}")
        return options[pick - 1]
    if len(options) == 1:
        return options[0]
    print(f"Several matches, choose a {what}:")
    for i, o in enumerate(options, 1):
        print(f"  {i}. {describe(o)}")
    if not sys.stdin.isatty():
        raise UserError("refine the query or add --pick N")
    try:
        answer = input("Number (Enter = cancel): ").strip()
    except EOFError:
        raise UserError("refine the query or add --pick N") from None
    if not answer:
        raise UserError("cancelled")
    if not answer.isdigit() or not 1 <= int(answer) <= len(options):
        raise UserError("invalid number")
    return options[int(answer) - 1]


# --- food lookup ----------------------------------------------------------------

def unit_from_description(description, name, units):
    """'127 g Egg' -> 'g', '1 1/2 servings Milk' -> 'serving'."""
    prefix = description[: -len(name)] if name and description.endswith(name) else description
    m = re.match(r"^\s*[\d\s.,/]+\s*(\S+)", prefix)
    unit = m.group(1) if m else ""
    if len(unit) > 1 and unit.endswith("s"):
        unit = unit[:-1]
    # FatSecret localizes units for some regions ("127 гs Яйцо")
    return {"г": "g", "мл": "ml", "порция": "serving", "克": "g", "毫升": "ml", "份": "serving"}.get(unit, unit)


class KnownFood(dict):
    """food_id, serving_id, name, unit, units (usual portion), count, last_date"""

    def describe(self):
        unit = self.get("unit") or "units"
        stats = f", logged {self['count']} times" if self.get("count") else ""
        return f"{self['name']} — usually {fmt_num(self.get('units'), 2)} {unit}{stats}"


def known_foods(client=None, meal=None):
    """Foods you have logged before: local export (data/food_entries.csv) + live recent/most eaten/favorites.

    On the free API plan this is the only way to get IDs of non-US (e.g. Russian) products."""
    foods = {}
    path = DATA_DIR / "food_entries.csv"
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if meal and norm(r.get("meal")) != meal:
                    continue
                key = (r["food_id"], r["serving_id"])
                kf = foods.get(key)
                if kf is None:
                    kf = foods[key] = KnownFood(food_id=r["food_id"], serving_id=r["serving_id"], count=0,
                                                last_date="")
                kf["count"] += 1
                if r["date"] >= kf["last_date"]:
                    kf.update(last_date=r["date"], name=r["food_entry_name"], units=num(r["number_of_units"]),
                              unit=unit_from_description(r["food_entry_description"], r["food_entry_name"],
                                                         r["number_of_units"]))
    if client is not None:
        live = []
        for fetch in (lambda: client.favorite_foods(), lambda: client.recently_eaten(meal),
                      lambda: client.most_eaten(meal)):
            try:
                live += fetch()
            except Exception:  # live lists are a bonus; local history still works offline
                pass
        for f in live:
            key = (f["food_id"], f.get("serving_id", ""))
            if key not in foods:
                name = " ".join(x for x in (f.get("brand_name"), f.get("food_name")) if x)
                foods[key] = KnownFood(food_id=f["food_id"], serving_id=f.get("serving_id", ""), name=name,
                                       units=num(f.get("number_of_units")), unit="", count=0, last_date="")
    return sorted(foods.values(), key=lambda x: (x["count"], x.get("last_date", "")), reverse=True)


def find_food(client, query, pick=None, meal=None):
    candidates = [f for f in known_foods(client, meal) if matches(query, f.get("name"))]
    if not candidates:
        raise UserError(
            f"'{query}' not found in your history.\n"
            "  -> refresh the history: fatsecret export --all\n"
            "  -> or log the food once in the FatSecret app; after that it is available here\n"
            "  -> US-database foods can be found with: fatsecret search <english name>"
        )
    return choose(candidates[:15], KnownFood.describe, pick, "food")
