"""Minimal FatSecret Platform API client (OAuth 1.0, HMAC-SHA1), stdlib only."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

API_URL = "https://platform.fatsecret.com/rest/server.api"
REQUEST_TOKEN_URL = "https://authentication.fatsecret.com/oauth/request_token"
AUTHORIZE_URL = "https://authentication.fatsecret.com/oauth/authorize"
ACCESS_TOKEN_URL = "https://authentication.fatsecret.com/oauth/access_token"

EPOCH = date(1970, 1, 1)

# Human-readable hints for the API error codes you actually hit from the CLI.
ERROR_HINTS = {
    9: "access token is invalid: run `fatsecret auth` again",
    11: "daily request limit reached (5000 per day on the Basic plan)",
    21: "your FatSecret developer account restricts API access by IP address: see IP Restrictions on platform.fatsecret.com",
    106: "invalid ID. On the free plan non-US foods are only available from your own history",
    205: "weight can only be recorded for a date within 2 days of today",
    206: "weight can't be recorded for a date earlier than the last weigh-in",
    207: "the source day has no entries to copy",
    211: "food not found",
}


class FatSecretError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def to_date_int(d: date) -> int:
    return (d - EPOCH).days


def from_date_int(n) -> date:
    return EPOCH + timedelta(days=int(n))


def _enc(s) -> str:
    return urllib.parse.quote(str(s), safe="-._~")


def as_list(x):
    """FatSecret returns a dict instead of a list when there is a single item, and null for none."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def pluck(data, *path):
    """pluck(data, "foods", "food") -> list, tolerant of nulls along the way."""
    for key in path:
        if not isinstance(data, dict):
            return []
        data = data.get(key)
    return as_list(data)


class FatSecretClient:
    def __init__(self, consumer_key, consumer_secret, token=None, token_secret=None):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.token = token
        self.token_secret = token_secret

    # --- OAuth 1.0 signing -------------------------------------------------

    def _signed_params(self, method, url, params, token=None, token_secret=""):
        oauth = {
            "oauth_consumer_key": self.consumer_key,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_nonce": secrets.token_hex(16),
            "oauth_version": "1.0",
        }
        if token:
            oauth["oauth_token"] = token
        all_params = {**{k: v for k, v in params.items() if v is not None}, **oauth}
        normalized = "&".join(
            f"{_enc(k)}={_enc(v)}" for k, v in sorted((str(k), str(v)) for k, v in all_params.items())
        )
        base = "&".join([method.upper(), _enc(url), _enc(normalized)])
        key = f"{_enc(self.consumer_secret)}&{_enc(token_secret or '')}"
        sig = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
        all_params["oauth_signature"] = sig
        return all_params

    def _http(self, method, url, params):
        body = urllib.parse.urlencode(params)
        if method == "GET":
            req = urllib.request.Request(f"{url}?{body}", method="GET")
        else:
            req = urllib.request.Request(
                url, data=body.encode(), method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise FatSecretError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')}") from None
        except urllib.error.URLError as e:
            raise FatSecretError(f"can't reach FatSecret (no network access?): {e.reason}") from None

    # --- 3-legged auth flow ------------------------------------------------

    def get_request_token(self, callback="oob"):
        params = self._signed_params("POST", REQUEST_TOKEN_URL, {"oauth_callback": callback})
        data = dict(urllib.parse.parse_qsl(self._http("POST", REQUEST_TOKEN_URL, params)))
        if "oauth_token" not in data:
            raise FatSecretError(f"Unexpected request_token response: {data}")
        return data["oauth_token"], data["oauth_token_secret"]

    @staticmethod
    def authorize_url(request_token):
        return f"{AUTHORIZE_URL}?oauth_token={_enc(request_token)}"

    def get_access_token(self, request_token, request_token_secret, verifier):
        params = self._signed_params(
            "GET", ACCESS_TOKEN_URL, {"oauth_verifier": verifier},
            token=request_token, token_secret=request_token_secret,
        )
        data = dict(urllib.parse.parse_qsl(self._http("GET", ACCESS_TOKEN_URL, params)))
        if "oauth_token" not in data:
            raise FatSecretError(f"Unexpected access_token response: {data}")
        return data["oauth_token"], data["oauth_token_secret"]

    # --- generic call ------------------------------------------------------

    def call(self, api_method, http_method="GET", **params):
        params = {"method": api_method, "format": "json", **params}
        signed = self._signed_params(http_method, API_URL, params, self.token, self.token_secret)
        data = json.loads(self._http(http_method, API_URL, signed))
        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            code = int(err.get("code", 0) or 0)
            msg = f"API error {code}: {err.get('message')}"
            if code in ERROR_HINTS:
                msg += f"\n  → {ERROR_HINTS[code]}"
            raise FatSecretError(msg, code)
        return data

    def post(self, api_method, **params):
        return self.call(api_method, "POST", **params)

    # --- food diary --------------------------------------------------------

    def food_entries(self, d: date):
        return pluck(self.call("food_entries.get.v2", date=to_date_int(d)), "food_entries", "food_entry")

    def food_entry(self, entry_id):
        items = pluck(self.call("food_entries.get.v2", food_entry_id=entry_id), "food_entries", "food_entry")
        if not items:
            raise FatSecretError(f"entry {entry_id} not found")
        return items[0]

    def food_entries_month(self, d: date):
        """Daily totals for days with entries in the month containing `d`."""
        return pluck(self.call("food_entries.get_month.v2", date=to_date_int(d)), "month", "day")

    def create_food_entry(self, food_id, serving_id, units, name, meal, d: date):
        r = self.post("food_entry.create", food_id=food_id, serving_id=serving_id,
                      number_of_units=units, food_entry_name=name, meal=meal, date=to_date_int(d))
        return r["food_entry_id"]["value"]

    def edit_food_entry(self, entry_id, **fields):
        self.post("food_entry.edit", food_entry_id=entry_id, **fields)

    def delete_food_entry(self, entry_id):
        self.post("food_entry.delete", food_entry_id=entry_id)

    def copy_food_entries(self, from_d: date, to_d: date, meal=None):
        self.post("food_entries.copy", from_date=to_date_int(from_d), to_date=to_date_int(to_d), meal=meal)

    def copy_saved_meal(self, saved_meal_id, meal, d: date):
        self.post("food_entries.copy_saved_meal", saved_meal_id=saved_meal_id, meal=meal, date=to_date_int(d))

    # --- foods ---------------------------------------------------------------

    def most_eaten(self, meal=None):
        return pluck(self.call("foods.get_most_eaten.v2", meal=meal), "foods", "food")

    def recently_eaten(self, meal=None):
        return pluck(self.call("foods.get_recently_eaten.v2", meal=meal), "foods", "food")

    def favorite_foods(self):
        return pluck(self.call("foods.get_favorites.v2"), "foods", "food")

    def add_favorite_food(self, food_id, serving_id=None, units=None):
        self.post("food.add_favorite", food_id=food_id, serving_id=serving_id, number_of_units=units)

    def delete_favorite_food(self, food_id, serving_id=None, units=None):
        self.post("food.delete_favorite", food_id=food_id, serving_id=serving_id, number_of_units=units)

    def search_foods(self, query, page=0, max_results=20):
        r = self.call("foods.search", search_expression=query, page_number=page, max_results=max_results)
        return pluck(r, "foods", "food"), int((r.get("foods") or {}).get("total_results", 0) or 0)

    def food(self, food_id):
        return self.call("food.get.v5", food_id=food_id)["food"]

    # --- saved meals ---------------------------------------------------------

    def saved_meals(self, meal=None):
        return pluck(self.call("saved_meals.get.v2", meal=meal), "saved_meals", "saved_meal")

    def create_saved_meal(self, name, description=None, meals=None):
        r = self.post("saved_meal.create", saved_meal_name=name,
                      saved_meal_description=description, meals=meals)
        return r["saved_meal_id"]["value"]

    def edit_saved_meal(self, saved_meal_id, **fields):
        self.post("saved_meal.edit", saved_meal_id=saved_meal_id, **fields)

    def delete_saved_meal(self, saved_meal_id):
        self.post("saved_meal.delete", saved_meal_id=saved_meal_id)

    def saved_meal_items(self, saved_meal_id):
        return pluck(self.call("saved_meal_items.get.v2", saved_meal_id=saved_meal_id),
                     "saved_meal_items", "saved_meal_item")

    def add_saved_meal_item(self, saved_meal_id, food_id, serving_id, units, name):
        r = self.post("saved_meal_item.add", saved_meal_id=saved_meal_id, food_id=food_id,
                      serving_id=serving_id, number_of_units=units, saved_meal_item_name=name)
        return r["saved_meal_item_id"]["value"]

    def edit_saved_meal_item(self, item_id, **fields):
        self.post("saved_meal_item.edit", saved_meal_item_id=item_id, **fields)

    def delete_saved_meal_item(self, item_id):
        self.post("saved_meal_item.delete", saved_meal_item_id=item_id)

    # --- weight & profile ----------------------------------------------------

    def profile(self):
        return self.call("profile.get").get("profile") or {}

    def weights_month(self, d: date):
        return pluck(self.call("weights.get_month.v2", date=to_date_int(d)), "month", "day")

    def update_weight(self, kg, d: date, comment=None, goal_kg=None, height_cm=None):
        self.post("weight.update", current_weight_kg=kg, date=to_date_int(d), comment=comment,
                  goal_weight_kg=goal_kg, current_height_cm=height_cm)

    # --- exercise --------------------------------------------------------------

    def exercise_types(self):
        return pluck(self.call("exercises.get.v2"), "exercises", "exercise")

    def exercise_entries(self, d: date):
        return pluck(self.call("exercise_entries.get.v2", date=to_date_int(d)),
                     "exercise_entries", "exercise_entry")

    def exercise_month(self, d: date):
        return pluck(self.call("exercise_entries.get_month.v2", date=to_date_int(d)), "month", "day")

    def shift_exercise(self, d: date, to_id, from_id, minutes, to_name=None, kcal=None, from_name=None):
        self.post("exercise_entry.edit", date=to_date_int(d), shift_to_id=to_id, shift_from_id=from_id,
                  minutes=minutes, shift_to_name=to_name, kcal=kcal, shift_from_name=from_name)

    def commit_exercise_day(self, d: date):
        self.post("exercise_entries.commit_day", date=to_date_int(d))

    def save_exercise_template(self, days_mask, d: date):
        self.post("exercise_entries.save_template", days=days_mask, date=to_date_int(d))

    # --- recipes (US dataset, English) ---------------------------------------

    def search_recipes(self, query, max_results=20, **filters):
        r = self.call("recipes.search.v3", search_expression=query, max_results=max_results, **filters)
        return pluck(r, "recipes", "recipe"), int((r.get("recipes") or {}).get("total_results", 0) or 0)

    def recipe(self, recipe_id):
        return self.call("recipe.get.v2", recipe_id=recipe_id)["recipe"]

    def favorite_recipes(self):
        return pluck(self.call("recipes.get_favorites.v2"), "recipes", "recipe")

    def add_favorite_recipe(self, recipe_id):
        self.post("recipe.add_favorite", recipe_id=recipe_id)

    def delete_favorite_recipe(self, recipe_id):
        self.post("recipe.delete_favorite", recipe_id=recipe_id)
