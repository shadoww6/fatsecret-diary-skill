# First-time setup (walk the user through it step by step)

Take one step at a time and wait for the user's reply after each. Use plain language:
the user may not be technical at all. Speak the user's language.

Before you start, run `fs check`.
- "No API keys" means start from step 1.
- "API keys are set, but the account is not connected" means go to step 3.

## Step 1. A FatSecret account with a username and password

The user needs a regular FatSecret account, the same one they use in the phone app. Check two things:
- **Do they know their username** (Member name)? It is shown in the app's profile, on the "Me" tab.
- **Do they have a password?** If they sign in to the app with Google, Apple or Facebook, there may be no password.
  In that case they need to set one on https://www.fatsecret.com via "Forgot password?" (using the account's email).

Step 3 can't be done without the username and password.

## Step 2. Free FatSecret developer keys

This is a separate registration. It is free, takes about 5 minutes and is done once.

1. Open https://platform.fatsecret.com/register and fill in the form.
   - In "Business/Organization/Startup" you can write "Personal use".
   - Password: at least 8 characters, with an upper-case letter, a lower-case letter, a digit and a symbol.
2. Confirm your email if a message arrives, and sign in at https://platform.fatsecret.com.
3. Open the API keys section (**My Account → API Key**).
4. Find the **OAuth 1.0** block and copy the **Consumer Key** and **Consumer Secret**.
   - Don't mix it up with the OAuth 2.0 block: it has "Client ID" and "Client Secret", and the Client Secret
     **does not work** here.
5. Send them to the chat as `Consumer Key:Consumer Secret` (separated by a colon).
   - Developer keys alone don't give access to the diary, so sending them in the chat is fine.
   - Still, don't publish them.

Once you have the keys, run `fs connect "KEY:SECRET"`.

## Step 3. Allow access to the diary

1. Run `fs auth --no-wait`. It prints a link.
2. Give the user the link and explain:
   - open it **right away**, the link expires in a few minutes;
   - sign in: **Member name** is the **username**, not the email;
   - click "Allow";
   - FatSecret shows a **PIN**, send it to the chat. If the PIN isn't visible, it is in the address bar
     after `oauth_verifier=`.
3. When you get the PIN, run `fs auth --pin <PIN>`.
   - If the PIN expired or an error came back, repeat step 3 with a new link.
4. The command prints the **connection string**. Show it to the user once and explain:
   - it is the key to their diary, never share it;
   - so they don't have to reconnect in every new chat, create a Claude **Project** (e.g. "Food diary")
     and paste this line into the **project instructions**:
     `FatSecret: <connection string>`;
   - after that, keep all food chats in that project.

## Step 4. Check

Run `fs check` and `fs diary`. Show the user today's diary and a few examples of what they can ask:
- "log 2 eggs and coffee with milk for breakfast";
- "what did I eat yesterday";
- "my average protein this week";
- "chart my weight for the last month".

---

## Internet access (on a network error)

By default, skill code in Claude can only reach package registries (pip, npm). The settings need to be changed
once (on claude.ai or in the desktop app):

1. **Settings → Capabilities**.
2. Turn on **Code execution and file creation**.
3. Turn on **Allow network egress** (internet access).
4. In **Domain allowlist**, add `platform.fatsecret.com` and `authentication.fatsecret.com`,
   or choose "All domains".

Then start a **new chat**: the settings apply to new chats.

## Error 21: Invalid IP address

The error means the user's FatSecret developer account has an IP allowlist, and Claude connects from a
different address. The error text shows the address the request came from.

1. On https://platform.fatsecret.com open the key settings and find the **IP Restrictions** section.
2. If restrictions can be turned off, turn them off. If not, add the address from the error.
   - Claude's addresses may change, so the error may come back.
   - If it keeps coming back, report it to the skill's author (Issues on GitHub).

## Troubleshooting

| Symptom | What to do |
|---|---|
| "Login failed" when signing in to FatSecret | Member name needs the username, not the email. If they used Google or Apple, set a password (step 1) |
| The authorization link expired | Repeat step 3 |
| `API error 9` | Access was revoked: repeat step 3 and update the line in the project instructions |
| `API error 106` | The food is not from the US database: take it from the history (`fs foods`) |
| `API error 205/206` | Weight can only be recorded for today ±2 days and not before the last weigh-in |
| `API error 11` | The daily limit of 5000 requests is used up, wait until tomorrow |
| "not found in your history" | See items 3–4 of "Logging food" in SKILL.md |
