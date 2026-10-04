"""Export diary data to CSV files in data/ (upsert, so re-runs never duplicate rows)."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from .client import from_date_int
from .config import DATA_DIR
from .util import num

ENTRY_FIRST_COLS = [
    "date", "meal", "food_entry_name", "food_entry_description", "number_of_units",
    "calories", "protein", "fat", "carbohydrate", "fiber", "sugar",
]
NUTRIENTS = [
    "calories", "protein", "fat", "carbohydrate", "fiber", "sugar", "saturated_fat",
    "polyunsaturated_fat", "monounsaturated_fat", "cholesterol", "sodium", "potassium",
]


def month_starts(start: date, end: date):
    d = start.replace(day=1)
    while d <= end:
        yield d
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def prev_month(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def find_history_start(client, empty_months_to_stop=6) -> date:
    """Walk back month by month until N consecutive months have neither food nor weight entries."""
    m, first, empty = date.today().replace(day=1), date.today(), 0
    while empty < empty_months_to_stop:
        days = client.food_entries_month(m) + client.weights_month(m)
        if days:
            first, empty = min(from_date_int(d["date_int"]) for d in days), 0
        else:
            empty += 1
        m = prev_month(m)
    return first


def upsert_csv(path: Path, rows, key_cols, first_cols, replace_dates):
    """Merge rows into CSV by key. Existing rows for `replace_dates` are dropped first,
    so entries deleted in FatSecret also disappear from the export."""
    existing = []
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            existing = [r for r in csv.DictReader(f) if r.get("date") not in replace_dates]
    merged = {tuple(r.get(k, "") for k in key_cols): r for r in existing}
    for r in rows:
        merged[tuple(str(r.get(k, "")) for k in key_cols)] = r

    cols = list(first_cols)
    for r in merged.values():
        cols += [c for c in r if c not in cols]
    out = sorted(merged.values(), key=lambda r: tuple(str(r.get(k, "")) for k in key_cols))

    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig so Excel opens Cyrillic food names correctly
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    return len(out)


def export(client, start: date, end: date, exercise=False, log=print):
    in_range = lambda d: start <= d <= end
    all_dates = {(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)}

    entries, weights, exercises = [], [], []
    for m in month_starts(start, end):
        log(f"  {m:%Y-%m}…")
        for day in client.food_entries_month(m):
            d = from_date_int(day["date_int"])
            if in_range(d):
                for e in client.food_entries(d):
                    e = {k: v for k, v in e.items() if not isinstance(v, (dict, list))}
                    e["date"] = d.isoformat()
                    entries.append(e)
        for w in client.weights_month(m):
            d = from_date_int(w["date_int"])
            if in_range(d):
                weights.append({"date": d.isoformat(), "weight_kg": w.get("weight_kg"),
                                "comment": w.get("weight_comment", "")})
        if exercise:
            for x in client.exercise_month(m):
                d = from_date_int(x["date_int"])
                if in_range(d):
                    exercises.append({"date": d.isoformat(), "calories": x.get("calories")})

    # Daily totals computed from entries (richer than the get_month summary).
    daily = {}
    for e in entries:
        t = daily.setdefault(e["date"], {"date": e["date"], **{n: 0.0 for n in NUTRIENTS}, "entries": 0})
        for n in NUTRIENTS:
            t[n] += num(e.get(n))
        t["entries"] += 1
    for t in daily.values():
        for n in NUTRIENTS:
            t[n] = round(t[n], 2)

    result = {
        "food_entries.csv": upsert_csv(DATA_DIR / "food_entries.csv", entries, ["date", "food_entry_id"],
                                       ENTRY_FIRST_COLS, all_dates),
        "daily_totals.csv": upsert_csv(DATA_DIR / "daily_totals.csv", daily.values(), ["date"],
                                       ["date", *NUTRIENTS, "entries"], all_dates),
        "weights.csv": upsert_csv(DATA_DIR / "weights.csv", weights, ["date"],
                                  ["date", "weight_kg", "comment"], all_dates),
    }
    if exercise:
        result["exercise.csv"] = upsert_csv(DATA_DIR / "exercise.csv", exercises, ["date"],
                                            ["date", "calories"], all_dates)
    return {"entries": len(entries), "days": len(daily), "weights": len(weights), "files": result}
