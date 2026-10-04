# Command reference

Run commands as `python3 scripts/fatsecret.py <command>`. Below, that is shortened to `fs`.

**Dates:**
- `2026-10-03`, `03.10`, `03.10.2026`;
- `today`, `yesterday`, `tomorrow`;
- `-3` (3 days ago).
- Russian and Chinese day names work too (`вчера`, `昨天`).

**Meals:** `breakfast` / `lunch` / `dinner` / `other`. Russian and Chinese meal names are understood as well.

## Connection

| Command | What it does |
|---|---|
| `fs check` | check keys, token and the connection to FatSecret |
| `fs connect "KEY:SECRET[:TOKEN:TOKEN_SECRET]"` | save keys or a connection string (to `~/.fatsecret/.env`) |
| `fs auth --no-wait` → `fs auth --pin <PIN>` | connect the account: link, sign-in, PIN. Prints the connection string |
| `fs profile` | last weight, goal, height |

## Food diary

| Command | What it does |
|---|---|
| `fs diary [date]` | entries for a day by meal, with ids and nutrition |
| `fs foods [word] [--limit N]` | foods from the user's history: usual portion, unit, times logged, food_id/serving_id |
| `fs add <words…> [amount] [-m meal] [-d date] [-n name] [--pick N]` | log a food from the history. The amount is in the unit from the "usually" column of `foods`; with no amount, the usual portion is logged |
| `fs add --food-id ID --grams G -n "Name" [-m] [-d]` | log a US-database food in grams |
| `fs add --food-id ID --serving-id SID <count> -n "Name"` | log a US-database food by a specific serving |
| `fs edit <id> [--amount N] [-m meal] [-n name] [-d date]` | change an entry. With `-d` the entry is re-created and its id changes |
| `fs delete <id> [id…]` | delete entries |
| `fs copy <from> [to] [-m meal]` | copy a day or a meal to another date (default: today) |

## FatSecret database search (US only, English)

| Command | What it does |
|---|---|
| `fs search <english words> [--generic] [--page N] [--limit N]` | foods with food_id and type (Generic/Brand). `--generic` keeps only non-branded foods |
| `fs food <food_id>` | a food's servings: serving_id, weight, nutrition |
| `fs recipes search <words>` / `fs recipes show <id>` | recipes |
| `fs recipes favs` / `fav-add <id>` / `fav-remove <id>` | favorite recipes |

## Saved meals and favorites

| Command | What it does |
|---|---|
| `fs saved list` | saved meals |
| `fs saved create "Name" [--from date] [-m meal] [--for breakfast,other]` | create a saved meal, optionally straight from the diary |
| `fs saved show <name\|id>` | items of a saved meal (with item ids) |
| `fs saved add <saved meal> <food…> [amount]` | add a food from the history to a saved meal |
| `fs saved remove <item_id>` / `rename <saved meal> "New"` / `delete <saved meal>` | remove an item, rename, delete |
| `fs saved log <saved meal> [-m meal] [-d date]` | log a saved meal to the diary |
| `fs fav list` / `fav add <food…> [--force]` / `fav remove <food…>` | favorite foods. A non-US food can't be removed via the API afterwards |

## Weight, activity, stats

| Command | What it does |
|---|---|
| `fs weight` / `fs weight --days 90` | weight history and goal |
| `fs weight <kg> [-d date] [-c comment]` | record weight (today ±2 days, not before the last weigh-in) |
| `fs stats [--days 14] [--from date --to date]` | calories, macros and weight by day, with averages |
| `fs exercise day [date]` / `types [word]` | activity for a day, list of activity types |
| `fs exercise add <type> <minutes> [--from id] [--kcal N]` | add activity (minutes are moved from resting) |
| `fs exercise commit [date]` / `template mon,wed,fri` | commit a day, save a template |

## Export and other

| Command | What it does |
|---|---|
| `fs export [--days N \| --from date --to date \| --all] [--exercise]` | CSV files in `~/.fatsecret/data/` (or `$FATSECRET_DATA_DIR`) |
| `fs api <method> [key=value…] [--post]` | raw call of any FatSecret API method (dates are days since 1970-01-01) |
