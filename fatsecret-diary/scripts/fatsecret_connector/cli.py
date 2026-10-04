"""Command line interface: `fatsecret <command>`. Run `fatsecret -h` or `fatsecret <command> -h`."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

from . import config
from .client import FatSecretError, from_date_int
from .config import ConfigError, make_client
from .export import export, find_history_start, month_starts
from .util import (
    MEAL_NAMES, MEALS, UserError, choose, find_food, fmt_num, known_foods, macro_line, matches, norm, num,
    parse_date, parse_meal, parse_number, print_table, split_query_amount,
)


def meal_of(entry):
    return norm(entry.get("meal")) or "other"


# --- connection & profile --------------------------------------------------------

def cmd_auth(a):
    if a.pin:
        token, secret = config.pop_pending_auth()
        return _finish_auth(token, secret, a.pin)
    client = make_client(authorized=False)
    token, secret = client.get_request_token()
    print("1. Open this link right away (it expires in a few minutes), sign in to FatSecret and allow access:\n")
    print("   " + client.authorize_url(token) + "\n")
    print("   'Member name' is your FatSecret username, not your email.")
    if a.no_wait:
        config.save_pending_auth(token, secret)
        print("2. Then run:  fatsecret auth --pin <PIN>")
        return
    pin = input("2. Enter the PIN shown by FatSecret: ").strip()
    _finish_auth(token, secret, pin)


def _finish_auth(token, secret, pin):
    access, access_secret = make_client(authorized=False).get_access_token(token, secret, pin)
    config.save_env({"FATSECRET_ACCESS_TOKEN": access, "FATSECRET_ACCESS_SECRET": access_secret})
    print(f"Done, your account is connected. Token saved to {config.ENV_FILE}")
    print("\nConnection string (keep it somewhere safe, e.g. in your Claude project instructions;\n"
          "it gives access to your diary, don't share it):\n")
    print("  " + config.connection_string())


def cmd_connect(a):
    values = config.parse_connection(a.connection)
    config.save_env(values)
    if len(values) == 2:
        print("API keys saved. Now connect your account: fatsecret auth")
    else:
        cmd_check(a)


def cmd_check(a):
    missing = [v for v in config.ALL_VARS if not config.get(v)]
    if set(missing) & set(config.KEY_VARS):
        raise ConfigError("no API keys: fatsecret connect KEY:SECRET")
    if missing:
        raise ConfigError("API keys are set, but the account is not connected: fatsecret auth")
    p = make_client().profile()
    weight = f", last weight {fmt_num(p['last_weight_kg'])} kg" if p.get("last_weight_kg") else ""
    print(f"Connection works{weight}.")


def cmd_profile(a):
    p = make_client().profile()
    if p.get("last_weight_kg"):
        print(f"Last weight: {fmt_num(p['last_weight_kg'])} kg ({from_date_int(p['last_weight_date_int'])})")
    if p.get("goal_weight_kg"):
        print(f"Goal:        {fmt_num(p['goal_weight_kg'])} kg")
    if p.get("height_cm"):
        print(f"Height:      {fmt_num(p['height_cm'])} cm")
    print(f"Units:       {p.get('weight_measure', '?')}, {p.get('height_measure', '?')}")


# --- food diary -----------------------------------------------------------------

def cmd_diary(a):
    d = parse_date(a.date)
    entries = make_client().food_entries(d)
    print(f"Diary for {d:%Y-%m-%d}" + ("" if entries else ": no entries"))
    total = {}
    for meal in MEALS:
        items = [e for e in entries if meal_of(e) == meal]
        if not items:
            continue
        sub = {k: sum(num(e.get(k)) for e in items) for k in ("calories", "protein", "fat", "carbohydrate")}
        print(f"\n{MEAL_NAMES[meal]}  ({macro_line(sub).strip()})")
        for e in items:
            print(f"  {e['food_entry_id']:>12}  {macro_line(e)}  {e['food_entry_description']}")
        for k, v in sub.items():
            total[k] = total.get(k, 0) + v
    if entries:
        print(f"\nTotal: {macro_line(total).strip()}")


def grams_serving(food, grams):
    """Pick a serving to log `grams` of a US-database food: (serving_id, number_of_units)."""
    servings = [s for s in (food.get("servings") or {}).get("serving", []) if s.get("serving_id") != "0"]
    for s in servings:  # a per-gram serving ("100 g" with measurement "g") takes grams directly
        if s.get("measurement_description") == "g" and s.get("metric_serving_unit") == "g":
            return s["serving_id"], round(grams * num(s["number_of_units"]) / num(s["metric_serving_amount"]), 3)
    for s in servings:
        if s.get("metric_serving_unit") == "g" and num(s.get("metric_serving_amount")) > 0:
            return s["serving_id"], round(grams / num(s["metric_serving_amount"]), 3)
    raise UserError("this food has no gram-based servings, use --serving-id (see: fatsecret food <food_id>)")


def cmd_add(a):
    client = make_client()
    d = parse_date(a.date)
    meal = parse_meal(a.meal, default_by_time=True)
    if a.food_id:
        amount = parse_number(a.words[-1]) if a.words else 1
        if a.grams is not None:
            serving_id, amount = grams_serving(client.food(a.food_id), a.grams)
        elif a.serving_id:
            serving_id = a.serving_id
        else:
            raise UserError("--food-id needs --serving-id or --grams (servings: fatsecret food <food_id>)")
        name = a.name or client.food(a.food_id)["food_name"]
        food = {"food_id": a.food_id, "serving_id": serving_id, "name": name, "unit": "", "units": amount}
    else:
        query, amount = split_query_amount(a.words)
        if not query:
            raise UserError("name a food, e.g.: fatsecret add milk 1.5")
        food = find_food(client, query, a.pick)
        if amount is None:
            amount = food["units"]
    if not amount or amount <= 0:
        raise UserError("amount must be greater than zero")
    name = a.name or food["name"]
    entry_id = client.create_food_entry(food["food_id"], food["serving_id"], amount, name, meal, d)
    e = client.food_entry(entry_id)
    print(f"Added to {MEAL_NAMES[meal]} on {d:%Y-%m-%d}: {e['food_entry_description']}")
    print(f"  {macro_line(e).strip()}   (id {entry_id}; undo: fatsecret delete {entry_id})")


def cmd_edit(a):
    client = make_client()
    e = client.food_entry(a.entry_id)
    fields = {}
    if a.amount is not None:
        fields["number_of_units"] = parse_number(a.amount)
    if a.meal:
        fields["meal"] = parse_meal(a.meal)
    if a.name:
        fields["food_entry_name"] = a.name
    if a.date:
        # the API can't move an entry to another date: re-create it there and delete the original
        new_id = client.create_food_entry(
            e["food_id"], e["serving_id"], fields.get("number_of_units", e["number_of_units"]),
            fields.get("food_entry_name", e["food_entry_name"]), fields.get("meal", meal_of(e)), parse_date(a.date))
        client.delete_food_entry(a.entry_id)
        print(f"Moved to {parse_date(a.date):%Y-%m-%d}, new id {new_id}")
        return
    if not fields:
        raise UserError("nothing to change: use --amount, --meal, --name or --date")
    client.edit_food_entry(a.entry_id, **fields)
    e = client.food_entry(a.entry_id)
    print(f"Updated: {e['food_entry_description']} [{e['meal']}]  {macro_line(e).strip()}")


def cmd_delete(a):
    client = make_client()
    for entry_id in a.entry_ids:
        e = client.food_entry(entry_id)
        client.delete_food_entry(entry_id)
        print(f"Deleted: {e['food_entry_description']} ({from_date_int(e['date_int']):%Y-%m-%d}, {e['meal']})")


def cmd_copy(a):
    client = make_client()
    src, dst = parse_date(a.from_date), parse_date(a.to_date)
    meal = parse_meal(a.meal)
    entries = [e for e in client.food_entries(src) if meal is None or meal_of(e) == meal]
    if not entries:
        raise UserError(f"no entries on {src:%Y-%m-%d}" + (f" in {MEAL_NAMES[meal]}" if meal else ""))
    meals = [m for m in MEALS if any(meal_of(e) == m for e in entries)]
    for m in meals:
        client.copy_food_entries(src, dst, m)
    print(f"Copied {len(entries)} entries ({', '.join(MEAL_NAMES[m] for m in meals)}) "
          f"from {src:%Y-%m-%d} to {dst:%Y-%m-%d}")


def cmd_stats(a):
    client = make_client()
    end = parse_date(a.to)
    start = parse_date(a.date_from) if a.date_from else end - timedelta(days=a.days - 1)
    food, weights = {}, {}
    for m in month_starts(start, end):
        food.update({from_date_int(x["date_int"]): x for x in client.food_entries_month(m)})
        weights.update({from_date_int(x["date_int"]): num(x["weight_kg"]) for x in client.weights_month(m)})
    days = sorted(d for d in set(food) | set(weights) if start <= d <= end)
    rows = []
    for d in days:
        f = food.get(d, {})
        rows.append([f"{d:%Y-%m-%d}", fmt_num(f.get("calories"), 0) if f else "", fmt_num(f.get("protein")) if f else "",
                     fmt_num(f.get("fat")) if f else "", fmt_num(f.get("carbohydrate")) if f else "",
                     fmt_num(weights[d]) if d in weights else ""])
    print(f"Period {start:%Y-%m-%d} – {end:%Y-%m-%d}\n")
    print_table(rows, ["date", "kcal", "protein", "fat", "carbs", "weight"])
    logged = [food[d] for d in days if d in food]
    if logged:
        avg = {k: sum(num(x[k]) for x in logged) / len(logged) for k in ("calories", "protein", "fat", "carbohydrate")}
        print(f"\nDays logged: {len(logged)} of {(end - start).days + 1}")
        print(f"Daily average: {macro_line(avg).strip()}")
    w = [weights[d] for d in days if d in weights]
    if len(w) >= 2:
        print(f"Weight: {fmt_num(w[0])} -> {fmt_num(w[-1])} kg ({w[-1] - w[0]:+.1f})")


# --- foods ----------------------------------------------------------------------

def cmd_foods(a):
    foods = known_foods(make_client(), parse_meal(a.meal))
    if a.query:
        foods = [f for f in foods if matches(" ".join(a.query), f.get("name"))]
    rows = [[f["name"][:45], f"{fmt_num(f.get('units'), 2)} {f.get('unit') or ''}".strip(), f["count"] or "",
             f.get("last_date", ""), f"{f['food_id']}/{f['serving_id']}"] for f in foods[: a.limit]]
    print_table(rows, ["food", "usually", "times", "last", "food_id/serving_id"])
    if len(foods) > a.limit:
        print(f"... and {len(foods) - a.limit} more. Narrow the query or use --limit")


def cmd_search(a):
    if a.generic:  # fetch a full page and keep only generic (non-branded) foods
        foods, total = make_client().search_foods(" ".join(a.query), a.page, 50)
        foods = [f for f in foods if f.get("food_type") == "Generic"][: a.limit]
    else:
        foods, total = make_client().search_foods(" ".join(a.query), a.page, a.limit)
    print(f"Found {total} (US database, search in English). Page {a.page}"
          + (", generic foods only" if a.generic else "") + ":\n")
    print_table([[f["food_id"], f.get("food_type", ""),
                  (f.get("brand_name") + ": " if f.get("brand_name") else "") + f["food_name"],
                  f.get("food_description", "")[:70]] for f in foods], ["food_id", "type", "food", "per serving"])
    print("\nServings and serving_id: fatsecret food <food_id>")


def cmd_food(a):
    f = make_client().food(a.food_id)
    print(f"{f.get('brand_name', '') + ': ' if f.get('brand_name') else ''}{f['food_name']}  ({f['food_url']})\n")
    servings = [s for s in (f.get("servings") or {}).get("serving", []) if s.get("serving_id") != "0"]
    print_table([[s["serving_id"], s["serving_description"],
                  f"{fmt_num(s.get('metric_serving_amount'))} {s.get('metric_serving_unit', '')}",
                  macro_line(s).strip()] for s in servings], ["serving_id", "serving", "weight", "nutrition"])
    if servings:
        print(f"\nAdd: fatsecret add --food-id {f['food_id']} --grams 100   "
              f"or  --serving-id {servings[0]['serving_id']} 1")


def cmd_fav(a):
    client = make_client()
    if a.action == "list":
        favs = client.favorite_foods()
        print_table([[f["food_name"], fmt_num(f.get("number_of_units"), 2), f"{f['food_id']}/{f.get('serving_id')}"]
                     for f in favs], ["food", "serving", "food_id/serving_id"]) if favs else print("No favorites")
        return
    query, amount = split_query_amount(a.words)
    food = find_food(client, query, a.pick)
    units = amount or food["units"]
    # On the Basic plan non-US foods can be added to favorites but not removed via the API
    # (food.delete_favorite fails with error 106, same as food.get for them).
    try:
        client.food(food["food_id"])
        us_food = True
    except FatSecretError:
        us_food = False
    if a.action == "add":
        if not us_food and not a.force:
            raise UserError("this is not a US-database food: it can be added to favorites, but removing it "
                            "will only be possible in the app. If that's fine, repeat with --force")
        client.add_favorite_food(food["food_id"], food["serving_id"], units)
        print(f"Added to favorites: {food['name']}")
    else:
        if not us_food:
            raise UserError("on the free plan the API can't remove non-US foods from favorites. "
                            "Remove it in the FatSecret app")
        client.delete_favorite_food(food["food_id"], food["serving_id"], units)
        print(f"Removed from favorites: {food['name']}")


# --- saved meals ------------------------------------------------------------------

def find_saved_meal(client, ref, pick=None):
    meals = client.saved_meals()
    found = [m for m in meals if m["saved_meal_id"] == ref] or [m for m in meals if matches(ref, m["saved_meal_name"])]
    if not found:
        raise UserError(f"saved meal '{ref}' not found. List: fatsecret saved list")
    return choose(found, lambda m: m["saved_meal_name"], pick, "saved meal")


def cmd_saved(a):
    client = make_client()
    act = a.action
    if act == "list":
        meals = client.saved_meals()
        if not meals:
            print("No saved meals. Create one from the diary: fatsecret saved create \"Name\" "
                  "--from yesterday --meal breakfast")
        for m in meals:
            print(f"{m['saved_meal_id']:>10}  {m['saved_meal_name']}  [{m.get('meals', '')}]  "
                  f"{m.get('saved_meal_description') or ''}")
    elif act == "show":
        m = find_saved_meal(client, a.ref, a.pick)
        print(f"{m['saved_meal_name']} (id {m['saved_meal_id']}):")
        for it in client.saved_meal_items(m["saved_meal_id"]):
            # the API returns the id as "saved_meal_item", not "saved_meal_item_id" as documented
            item_id = it.get("saved_meal_item_id") or it.get("saved_meal_item")
            print(f"  {item_id:>12}  {fmt_num(it['number_of_units'], 2):>6} x "
                  f"{it['saved_meal_item_name']}")
    elif act == "create":
        meals_for = ",".join(parse_meal(x).capitalize() for x in a.for_meals.split(",")) if a.for_meals else None
        mid = client.create_saved_meal(a.name, a.description, meals_for)
        n = 0
        if a.from_date:
            meal = parse_meal(a.meal)
            for e in client.food_entries(parse_date(a.from_date)):
                if meal is None or meal_of(e) == meal:
                    client.add_saved_meal_item(mid, e["food_id"], e["serving_id"], e["number_of_units"],
                                               e["food_entry_name"])
                    n += 1
        print(f"Created '{a.name}' (id {mid}), items: {n}")
    elif act == "add":
        m = find_saved_meal(client, a.ref)
        query, amount = split_query_amount(a.words)
        food = find_food(client, query, a.pick)
        client.add_saved_meal_item(m["saved_meal_id"], food["food_id"], food["serving_id"],
                                   amount or food["units"], food["name"])
        print(f"Added to '{m['saved_meal_name']}': {food['name']} x {fmt_num(amount or food['units'], 2)}")
    elif act == "remove":
        client.delete_saved_meal_item(a.item_id)
        print("Item removed from the saved meal")
    elif act == "rename":
        m = find_saved_meal(client, a.ref, a.pick)
        client.edit_saved_meal(m["saved_meal_id"], saved_meal_name=a.new_name)
        print(f"Renamed to '{a.new_name}'")
    elif act == "delete":
        m = find_saved_meal(client, a.ref, a.pick)
        client.delete_saved_meal(m["saved_meal_id"])
        print(f"Deleted '{m['saved_meal_name']}'")
    elif act == "log":
        m = find_saved_meal(client, a.ref, a.pick)
        meal = parse_meal(a.meal, default_by_time=True)
        d = parse_date(a.date)
        client.copy_saved_meal(m["saved_meal_id"], meal, d)
        print(f"'{m['saved_meal_name']}' logged to {MEAL_NAMES[meal]} on {d:%Y-%m-%d}")


# --- weight -------------------------------------------------------------------------

def cmd_weight(a):
    client = make_client()
    if a.kg is None:
        end = date.today()
        start = end - timedelta(days=a.days - 1)
        rows = []
        for m in month_starts(start, end):
            for w in client.weights_month(m):
                d = from_date_int(w["date_int"])
                if start <= d <= end:
                    rows.append([f"{d:%Y-%m-%d}", fmt_num(w["weight_kg"]), w.get("weight_comment", "")])
        print_table(rows, ["date", "kg", "comment"]) if rows else print("No weigh-ins in this period")
        goal = client.profile().get("goal_weight_kg")
        if goal:
            print(f"\nGoal: {fmt_num(goal)} kg")
        return
    kg = parse_number(a.kg)
    d = parse_date(a.date)
    client.update_weight(kg, d, a.comment, parse_number(a.goal) if a.goal else None,
                         parse_number(a.height) if a.height else None)
    print(f"Weight {fmt_num(kg)} kg recorded for {d:%Y-%m-%d}")


# --- exercise -----------------------------------------------------------------------

WEEKDAYS = {"sun": 1, "mon": 2, "tue": 4, "wed": 8, "thu": 16, "fri": 32, "sat": 64,
            "вс": 1, "пн": 2, "вт": 4, "ср": 8, "чт": 16, "пт": 32, "сб": 64,
            "周日": 1, "周一": 2, "周二": 4, "周三": 8, "周四": 16, "周五": 32, "周六": 64}


def cmd_exercise(a):
    client = make_client()
    d = parse_date(getattr(a, "date", None))
    if a.action == "day":
        items = client.exercise_entries(d)
        print(f"Activity for {d:%Y-%m-%d}:")
        print_table([[x["exercise_id"], x["exercise_name"], x["minutes"], x["calories"],
                      "template" if x.get("is_template_value") == "1" else ""] for x in items],
                    ["id", "activity", "min", "kcal", ""])
        print(f"\nTotal: {sum(int(num(x['calories'])) for x in items)} kcal")
    elif a.action == "types":
        types = [t for t in client.exercise_types() if not a.query or matches(" ".join(a.query), t["exercise_name"])]
        print_table([[t["exercise_id"], t["exercise_name"]] for t in types], ["id", "activity"])
    elif a.action == "add":
        query, minutes = split_query_amount(a.words)
        if not minutes:
            raise UserError("give the minutes, e.g.: fatsecret exercise add running 30")
        entries = client.exercise_entries(d)
        if a.from_id is not None:
            src = next((x for x in entries if x["exercise_id"] == str(a.from_id)), None)
        else:
            src = next((x for x in entries if x["exercise_name"] == "Resting"), None) or \
                max(entries, key=lambda x: int(num(x["minutes"])), default=None)
        if src is None:
            raise UserError("don't know where to take the minutes from: use --from <id> (see fatsecret exercise day)")
        if a.kcal is not None:
            to_id, to_name = 0, query
        else:
            types = [t for t in client.exercise_types() if t["exercise_id"] == query or matches(query, t["exercise_name"])]
            if not types:
                raise UserError(f"activity '{query}' not found (see: fatsecret exercise types). "
                                "Or define your own with --kcal <kcal>")
            t = choose(types, lambda t: t["exercise_name"], a.pick, "activity")
            to_id, to_name = t["exercise_id"], None
        client.shift_exercise(d, to_id, src["exercise_id"], int(minutes), to_name=to_name, kcal=a.kcal,
                              from_name=src["exercise_name"] if src["exercise_id"] == "0" else None)
        print(f"{int(minutes)} min moved from '{src['exercise_name']}' to '{to_name or t['exercise_name']}' "
              f"on {d:%Y-%m-%d}")
    elif a.action == "commit":
        client.commit_exercise_day(d)
        print(f"Activity for {d:%Y-%m-%d} saved")
    elif a.action == "template":
        keys = [x.strip().lower() for x in a.days.split(",")]
        keys = [k[:3] if k.isascii() else k for k in keys]  # "monday" -> "mon"
        if a.days.lower() in ("all", "все", "全部"):
            mask = 127
        elif all(k in WEEKDAYS for k in keys):
            mask = sum(WEEKDAYS[k] for k in keys)
        else:
            raise UserError("days must look like mon,wed,fri or all")
        client.save_exercise_template(mask, d)
        print(f"{d:%Y-%m-%d} saved as the activity template for: {a.days}")


# --- recipes ------------------------------------------------------------------------

def cmd_recipes(a):
    client = make_client()
    if a.action == "search":
        recipes, total = client.search_recipes(" ".join(a.query), a.limit)
        print(f"Found {total} (US database, English):\n")
        print_table([[r["recipe_id"], r["recipe_name"][:50],
                      fmt_num((r.get("recipe_nutrition") or {}).get("calories"), 0)] for r in recipes],
                    ["id", "recipe", "kcal/serving"])
    elif a.action == "show":
        r = client.recipe(a.recipe_id)
        print(f"{r['recipe_name']}  ({r.get('recipe_url', '')})")
        print(f"Servings: {r.get('number_of_servings')}, time: {r.get('preparation_time_min', '?')}+"
              f"{r.get('cooking_time_min', '?')} min")
        s = (r.get("serving_sizes") or {}).get("serving") or {}
        print(f"Per serving: {macro_line(s).strip()}\n\nIngredients:")
        for i in (r.get("ingredients") or {}).get("ingredient", []):
            print(f"  - {i['ingredient_description']}")
        print("\nDirections:")
        for st in (r.get("directions") or {}).get("direction", []):
            print(f"  {st['direction_number']}. {st['direction_description']}")
    elif a.action == "favs":
        for r in client.favorite_recipes():
            print(f"{r['recipe_id']:>10}  {r['recipe_name']}")
    elif a.action == "fav-add":
        client.add_favorite_recipe(a.recipe_id)
        print("Recipe added to favorites")
    elif a.action == "fav-remove":
        client.delete_favorite_recipe(a.recipe_id)
        print("Recipe removed from favorites")


# --- export & raw api -----------------------------------------------------------------

def cmd_export(a):
    client = make_client()
    end = parse_date(a.to)
    if a.all:
        print("Looking for the start of your history...")
        start = find_history_start(client)
    elif a.days:
        start = end - timedelta(days=a.days - 1)
    else:
        start = parse_date(a.date_from) if a.date_from else end - timedelta(days=29)
    print(f"Exporting {start:%Y-%m-%d} – {end:%Y-%m-%d} to {config.DATA_DIR}")
    r = export(client, start, end, exercise=a.exercise)
    print(f"\nEntries: {r['entries']} over {r['days']} days, weigh-ins: {r['weights']}")
    for name, n in r["files"].items():
        print(f"  {name}: {n} rows")


def cmd_api(a):
    params = {}
    for p in a.params:
        if "=" not in p:
            raise UserError(f"parameter '{p}' must look like key=value")
        k, v = p.split("=", 1)
        params[k] = v
    print(json.dumps(make_client().call(a.method, "POST" if a.post else "GET", **params),
                     ensure_ascii=False, indent=2))


# --- argument parsing -------------------------------------------------------------------

DATE_HELP = "date: 2026-10-03, 03.10, yesterday, -2 (default: today)"
MEAL_HELP = "breakfast / lunch / dinner / other"


def build_parser():
    p = argparse.ArgumentParser(prog="fatsecret", description="Your FatSecret diary from the command line")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="<command>")

    def cmd(name, func, help, aliases=()):
        sp = sub.add_parser(name, help=help, description=help, aliases=list(aliases))
        sp.set_defaults(func=func)
        return sp

    s = cmd("connect", cmd_connect, "save keys/token from a connection string KEY:SECRET[:TOKEN:TOKEN_SECRET]")
    s.add_argument("connection")
    cmd("check", cmd_check, "check that the connection works")
    s = cmd("auth", cmd_auth, "connect your FatSecret account (once)")
    s.add_argument("--no-wait", action="store_true", help="only print the link; finish later with --pin")
    s.add_argument("--pin", help="finish an authorization started with --no-wait")
    cmd("profile", cmd_profile, "weight, goal and height from your profile")

    s = cmd("diary", cmd_diary, "show the food diary for a day", ["d"])
    s.add_argument("date", nargs="?", help=DATE_HELP)

    s = cmd("add", cmd_add, "log a food from your history to the diary", ["a"])
    s.add_argument("words", nargs="*", metavar="food [amount]",
                   help="part of the name and amount in the serving's units (g, servings...). No amount = usual portion")
    s.add_argument("-m", "--meal", help=MEAL_HELP + " (default: by time of day)")
    s.add_argument("-d", "--date", help=DATE_HELP)
    s.add_argument("-n", "--name", help="custom entry name")
    s.add_argument("-p", "--pick", type=int, help="which match to use when several are found")
    s.add_argument("--food-id", help="log by food_id (e.g. from fatsecret search)")
    s.add_argument("--serving-id", help="serving_id for --food-id")
    s.add_argument("--grams", type=float, help="for --food-id: grams (a serving is picked automatically)")

    s = cmd("edit", cmd_edit, "change a diary entry")
    s.add_argument("entry_id")
    s.add_argument("--amount", help="new amount")
    s.add_argument("-m", "--meal", help=MEAL_HELP)
    s.add_argument("-n", "--name", help="new name")
    s.add_argument("-d", "--date", help="move to another date")

    s = cmd("delete", cmd_delete, "delete diary entries by id", ["rm"])
    s.add_argument("entry_ids", nargs="+")

    s = cmd("copy", cmd_copy, "copy entries from one day to another")
    s.add_argument("from_date", help="from (" + DATE_HELP + ")")
    s.add_argument("to_date", nargs="?", help="to (default: today)")
    s.add_argument("-m", "--meal", help="only this meal")

    s = cmd("stats", cmd_stats, "calories, macros and weight by day + averages")
    s.add_argument("--days", type=int, default=14, help="last N days (default 14)")
    s.add_argument("--from", dest="date_from")
    s.add_argument("--to")

    s = cmd("foods", cmd_foods, "foods from your history (with IDs and usual portions)")
    s.add_argument("query", nargs="*")
    s.add_argument("-m", "--meal")
    s.add_argument("--limit", type=int, default=40)

    s = cmd("search", cmd_search, "search the FatSecret database (US only on the free plan, English)")
    s.add_argument("query", nargs="+")
    s.add_argument("--page", type=int, default=0)
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--generic", action="store_true", help="only generic (non-branded) foods")

    s = cmd("food", cmd_food, "servings and nutrition of a food by food_id (US database)")
    s.add_argument("food_id")

    s = cmd("fav", cmd_fav, "favorite foods: list / add / remove")
    s.add_argument("action", choices=["list", "add", "remove"])
    s.add_argument("words", nargs="*", metavar="food [serving]")
    s.add_argument("-p", "--pick", type=int)
    s.add_argument("--force", action="store_true", help="add a non-US food (it can only be removed in the app)")

    s = cmd("saved", cmd_saved, "saved meals (templates)")
    ss = s.add_subparsers(dest="action", required=True, metavar="<action>")
    ss.add_parser("list", help="list saved meals")
    x = ss.add_parser("show", help="items of a saved meal")
    x.add_argument("ref", help="id or part of the name")
    x.add_argument("-p", "--pick", type=int)
    x = ss.add_parser("create", help="create (optionally from the diary)")
    x.add_argument("name")
    x.add_argument("--from", dest="from_date", help="take foods from the diary on this date")
    x.add_argument("-m", "--meal", help="... only from this meal")
    x.add_argument("--description")
    x.add_argument("--for", dest="for_meals", help="suitable meals, comma-separated: breakfast,other")
    x = ss.add_parser("add", help="add a food to a saved meal")
    x.add_argument("ref")
    x.add_argument("words", nargs="+", metavar="food [amount]")
    x.add_argument("-p", "--pick", type=int)
    x = ss.add_parser("remove", help="remove an item (id from show)")
    x.add_argument("item_id")
    x = ss.add_parser("rename", help="rename")
    x.add_argument("ref")
    x.add_argument("new_name")
    x.add_argument("-p", "--pick", type=int)
    x = ss.add_parser("delete", help="delete a saved meal")
    x.add_argument("ref")
    x.add_argument("-p", "--pick", type=int)
    x = ss.add_parser("log", help="log a saved meal to the diary")
    x.add_argument("ref")
    x.add_argument("-m", "--meal", help=MEAL_HELP + " (default: by time of day)")
    x.add_argument("-d", "--date", help=DATE_HELP)
    x.add_argument("-p", "--pick", type=int)

    s = cmd("weight", cmd_weight, "show weight history or record weight", ["w"])
    s.add_argument("kg", nargs="?", help="weight in kg; without it, show the history")
    s.add_argument("-d", "--date", help="only today ± 2 days and not before the last weigh-in")
    s.add_argument("-c", "--comment")
    s.add_argument("--goal", help="goal weight (required for the very first weigh-in)")
    s.add_argument("--height", help="height in cm (required for the very first weigh-in)")
    s.add_argument("--days", type=int, default=30, help="history period (default 30 days)")

    s = cmd("exercise", cmd_exercise, "activity diary")
    ss = s.add_subparsers(dest="action", required=True, metavar="<action>")
    x = ss.add_parser("day", help="activity for a day")
    x.add_argument("date", nargs="?")
    x = ss.add_parser("types", help="list of activity types")
    x.add_argument("query", nargs="*")
    x = ss.add_parser("add", help="add activity: move minutes from resting")
    x.add_argument("words", nargs="+", metavar="activity minutes")
    x.add_argument("-d", "--date")
    x.add_argument("--from", dest="from_id", type=int, help="id of the activity to take minutes from")
    x.add_argument("--kcal", type=int, help="custom activity: total kcal")
    x.add_argument("-p", "--pick", type=int)
    x = ss.add_parser("commit", help="commit a day (template -> actual entries)")
    x.add_argument("date", nargs="?")
    x = ss.add_parser("template", help="save a day as the template for weekdays")
    x.add_argument("days", help="mon,wed,fri or all")
    x.add_argument("-d", "--date", help="which day to use as the template")

    s = cmd("recipes", cmd_recipes, "FatSecret recipes (US database, English)")
    ss = s.add_subparsers(dest="action", required=True, metavar="<action>")
    x = ss.add_parser("search")
    x.add_argument("query", nargs="+")
    x.add_argument("--limit", type=int, default=20)
    x = ss.add_parser("show")
    x.add_argument("recipe_id")
    ss.add_parser("favs", help="favorite recipes")
    x = ss.add_parser("fav-add")
    x.add_argument("recipe_id")
    x = ss.add_parser("fav-remove")
    x.add_argument("recipe_id")

    s = cmd("export", cmd_export, "export diary, weight and activity to CSV")
    s.add_argument("--from", dest="date_from", help="from date (default: 30 days ago)")
    s.add_argument("--to", help="to date (default: today)")
    s.add_argument("--days", type=int, help="last N days")
    s.add_argument("--all", action="store_true", help="entire history")
    s.add_argument("--exercise", action="store_true", help="also export activity calories")

    s = cmd("api", cmd_api, "raw call of any API method (for experiments)")
    s.add_argument("method", help="e.g. food_entries.get.v2")
    s.add_argument("params", nargs="*", metavar="key=value")
    s.add_argument("--post", action="store_true", help="send as POST (for write methods)")
    return p


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (FatSecretError, ConfigError, UserError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
