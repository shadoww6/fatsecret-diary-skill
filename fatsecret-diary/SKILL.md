---
name: fatsecret-diary
description: Keeps the user's FatSecret food diary through the FatSecret Platform API — logs meals, edits and deletes entries, copies meals, records weight, shows calorie and macro stats, exports data to CSV and builds charts. Use when the user says what they ate or drank ("I had 2 eggs for breakfast", "log my lunch", "съела на завтрак творог", "早餐吃了两个鸡蛋"), asks about calories, protein, fat, carbs or weight, wants to see or analyze their food diary, mentions FatSecret, or asks to connect FatSecret.
---

# FatSecret food diary

This skill gives you access to the user's **personal FatSecret diary** through the CLI `scripts/fatsecret.py`
(pure Python 3.9+, no dependencies). Reply in the user's language, short and friendly. Skip JSON, ids and
technical details unless the user asks for them.

## Running

```bash
python3 <skill folder>/scripts/fatsecret.py <command> [args]
```

Below, the command is written as `fs <command>`.
- Help for any command: `fs <command> -h`.
- Full list of commands: [reference/commands.md](reference/commands.md).

## Step 0. Check the connection at the start of every new chat

The sandbox starts empty in every chat, so:

1. Run `fs check`.
2. If keys are missing, look for the user's **connection string**: 4 parts separated by colons, `KEY:SECRET:TOKEN:TOKEN_SECRET`.
   It can be in the project instructions, in a user message, or in the `FATSECRET_CONNECTION` variable.
   If you find it, run `fs connect "<string>"` and then `fs check` again.
3. If there is no string anywhere, the user is connecting for the first time. Walk them through
   [reference/setup.md](reference/setup.md).
4. A network error (`can't reach FatSecret`, `Name or service not known`, `403 … proxy`) means internet access
   is not allowed in the settings. Explain how to enable it ("Internet access" in setup.md).
5. `API error 21: Invalid IP address` means the user's FatSecret developer account restricts access by IP.
   See "Error 21" in setup.md.

**Security.** The connection string gives full access to the user's diary.
- Never repeat it in replies and never write it into files you hand to the user.
- The only exception is right after `fs auth --pin`. Show it **once** then and explain where to store it.

## Logging food

The user writes freely: "oatmeal 50 g and a banana for breakfast, coffee with milk".

1. Split the message into foods, amounts and meal. Meals: `breakfast`, `lunch`, `dinner`, `other` (snacks).
   - If no meal is given, the time of day picks it. If the meaning is clear ("for dinner"), pass `-m dinner` explicitly.
   - The date defaults to today. "Yesterday" is `-d yesterday`.
2. For each food, **search the user's history first**: `fs foods <word>`.
   - The "usually" column shows the usual portion and its **unit**: `g` is grams, `serving` is servings, etc.
   - The amount in `add` is **in that unit**. For example, the user said "200 g" but the food is stored in
     servings: convert using the serving description, or ask the user.
   - Found it: `fs add <part of name> <amount> -m <meal> --pick N`. When there are several matches,
     `--pick N` takes the N-th item from the `foods` list.
   - Without an amount, the user's usual portion is logged.
3. **The food is not in the history and it is a simple food** (egg, rice, chicken, cottage cheese, banana,
   oatmeal…):
   1. Translate the name to English and run `fs search <english name> --generic`.
      If nothing is found, drop `--generic` or simplify the name.
   2. Prefer `Generic` rows over `Brand`. Sanity-check the calories per 100 g.
   3. Log it: `fs add --food-id <id> --grams <g> -n "<name in the user's language>" -m <meal>`.
   4. If the user gave pieces rather than grams, check the servings with `fs food <id>` and use
      `--serving-id <id> <count>`.
4. **The food is a non-US branded product** (e.g. a local brand) and it is not in the history.
   The free plan can neither find nor create it. Offer the user two options:
   - log it **once in the FatSecret app** (by barcode), and after that you can log it;
   - or log a similar Generic food now, with the user's own name via `-n`.
5. After logging, report briefly: what was logged and where, its calories and macros, and the day's total.
   `fs diary` gives the day's total.
6. For a food photo, estimate the foods and grams, **show the estimate and wait for confirmation**, then log.

## Editing, deleting, copying

- View a day: `fs diary [date]`. It shows the entry ids.
- Change an entry: `fs edit <id> --amount N | -m <meal> | -n "<name>" | -d <date>`.
- Delete: `fs delete <id> [...]`.
- Copy: `fs copy yesterday [today] [-m breakfast]` ("same breakfast as yesterday").
- Saved meals (templates): `fs saved …` (create / add / log / show / delete).
  Handy for a recurring breakfast: `fs saved create "My breakfast" --from yesterday -m breakfast`,
  then `fs saved log "my breakfast" -m breakfast`.
- Before deleting several entries or copying a whole day, briefly confirm with the user what you are about to do.

## Weight and activity

- Record weight: `fs weight 64.3` (`-d yesterday` also works). FatSecret's limits:
  - the date must be within 2 days of today;
  - weight can't be recorded before the last weigh-in.
- Weight history: `fs weight --days 90`.
- Activity: `fs exercise day | types | add <type> <minutes> | commit`.
  If activity syncs from Samsung Health, Google Fit or similar, manual changes may be overwritten.

## Analysis and charts

- Quick summary: `fs stats --days 30` (calories and macros by day, averages, weight change).
- For charts and deeper analysis:
  1. Run `fs export --days 90` (or `--all`). The CSV files go to `~/.fatsecret/data/`:
     - `food_entries.csv` — every entry;
     - `daily_totals.csv` — daily sums;
     - `weights.csv` — weight.
  2. Build charts with pandas and matplotlib and save them where the user can download them
     (on Claude.ai that is `/mnt/user-data/outputs/`).
  3. User-created foods often have only calories and macros filled in, so sodium, sugar and fiber
     may be understated.

## Free (Basic) plan limits (don't promise more)

- Food search covers only the US database, in English. Creating custom foods, barcode search and
  autocomplete are not available.
- A non-US food can be added to favorites, but it can only be removed from them in the app.
- The limit is 5000 requests per day per key.

If something doesn't work: [reference/setup.md](reference/setup.md), "Troubleshooting".
