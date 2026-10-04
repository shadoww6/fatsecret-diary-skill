# FatSecret Diary — AI skill

**[English](#english) · [中文](#中文) · [Русский](#русский)**

---

## English

Tired of logging the same food in a dozen different places? This skill lets an AI assistant (Claude) keep your
[FatSecret](https://www.fatsecret.com) food diary for you. Just write in the chat:

> *"Oatmeal 50 g and a banana for breakfast, coffee with milk"*
> *"Same lunch as yesterday"*
> *"How much protein did I eat on average this week?"*
> *"Chart my weight and calories for the last month"*

Claude logs the food into **your own** FatSecret diary. The diary stays in sync with the FatSecret app on your
phone, and you can analyze everything in one place.

### What it can do

- Log meals from free text or a photo (photos are confirmed before logging).
- Find foods: your own history (any country, any brand) plus generic foods from the FatSecret database (eggs, rice, chicken…).
- Edit, delete and move entries; copy a meal or a whole day; reuse saved meals.
- Record weight; view and add activity.
- Stats: calories and macros by day, averages, weight trend.
- Export to CSV and build charts.

### What you need

- A **FatSecret account** with a username and password. If you sign in with Google or Apple, set a password
  via "Forgot password?" on fatsecret.com.
- A **Claude** account (claude.ai).
- About **15 minutes** for the one-time setup.

### Setup

**1. Get free FatSecret developer keys** (once)

1. Register at https://platform.fatsecret.com/register. In "Business/Organization" you can write "Personal use".
2. Sign in and open **My Account → API Key**.
3. In the **OAuth 1.0** block, copy the **Consumer Key** and **Consumer Secret**.
   - Not the OAuth 2.0 "Client Secret": it doesn't work here.

**2. Allow Claude to run code and reach FatSecret** (once)

In Claude, open **Settings → Capabilities** and:
- turn on **Code execution and file creation**;
- turn on **Allow network egress**;
- in **Domain allowlist**, add `platform.fatsecret.com` and `authentication.fatsecret.com` (or allow all domains).

**3. Install the skill** (once)

1. Download `fatsecret-diary.zip` from [Releases](../../releases/latest).
2. In Claude: **Settings → Capabilities → Skills → Upload skill** and select the zip.

**4. Connect your diary** (once)

1. Create a Claude **Project**, e.g. "Food diary".
2. Start a chat in it and write *"Connect my FatSecret"*.
3. Claude will ask for your keys, give you a sign-in link and ask for the PIN that FatSecret shows.
   - In "Member name" enter your FatSecret **username**, not your email.
4. At the end Claude shows a **connection string**.
   - Paste it into the **project instructions** as `FatSecret: <string>`.
   - After that, every chat in this project works right away.

> ⚠️ The connection string gives access to your diary. Don't share it with anyone.

### Limits of the free FatSecret plan

- The FatSecret search covers only the **US database** (generic foods work well).
- Local branded products can't be found by name. Log such a product **once in the FatSecret app**
  (e.g. by barcode); after that Claude can log it any time.
- Custom foods can't be created through the API.
- 5000 API requests per day per key, which is plenty for personal use.

### ChatGPT

ChatGPT uses the same skill format, but at the moment ChatGPT skills **have no internet access**, so they can't
reach FatSecret. When OpenAI enables network access for skills, this skill should work there too.

### Privacy

- The skill talks only to FatSecret.
- Your keys and token are stored only in your Claude project and in the chat sandbox.
- Nothing is sent anywhere else.

### For developers

The skill is a plain Python 3.9+ CLI with no dependencies:

```bash
pip install -e .
fatsecret connect "CONSUMER_KEY:CONSUMER_SECRET"
fatsecret auth
fatsecret diary
fatsecret add --food-id 33692 --grams 150 -n "Cottage cheese" -m breakfast
fatsecret stats --days 30
fatsecret export --all
```

- All commands: `fatsecret -h` or [fatsecret-diary/reference/commands.md](fatsecret-diary/reference/commands.md).
- Build the skill zip: `python build.py` (it creates `dist/fatsecret-diary.zip`).

---

## 中文

厌倦了在十几个地方重复记录同样的饮食吗？这个技能（skill）让 AI 助手（Claude）帮你维护
[FatSecret](https://www.fatsecret.com) 饮食日记。只需在聊天中写：

> *"早餐吃了 50 克燕麦片和一根香蕉，一杯加奶咖啡"*
> *"午餐和昨天一样"*
> *"这周我平均每天吃了多少蛋白质？"*
> *"画出我上个月的体重和热量图表"*

Claude 会把食物记录到**你自己的** FatSecret 日记中。日记与手机上的 FatSecret 应用保持同步，
所有数据都能在一个地方分析。

### 功能

- 根据文字或照片记录饮食（照片会先确认再记录）。
- 查找食物：你自己的历史记录（任何国家、任何品牌），以及 FatSecret 数据库中的通用食物（鸡蛋、米饭、鸡肉……）。
- 修改、删除、移动记录；复制一餐或一整天；使用保存的餐食模板。
- 记录体重；查看和添加运动。
- 统计：每日热量和三大营养素、平均值、体重趋势。
- 导出 CSV 并绘制图表。

### 你需要准备

- 一个有**用户名和密码**的 **FatSecret 账号**。如果你用 Google 或 Apple 登录，请在 fatsecret.com 上通过
  "Forgot password?" 设置密码。
- 一个 **Claude** 账号（claude.ai）。
- 大约 **15 分钟**完成一次性设置。

### 设置步骤

**1. 获取免费的 FatSecret 开发者密钥**（只需一次）

1. 在 https://platform.fatsecret.com/register 注册。"Business/Organization" 一栏可以填写 "Personal use"。
2. 登录后打开 **My Account → API Key**。
3. 在 **OAuth 1.0** 区块中复制 **Consumer Key** 和 **Consumer Secret**。
   - 不是 OAuth 2.0 的 "Client Secret"，它在这里不能用。

**2. 允许 Claude 运行代码并访问 FatSecret**（只需一次）

在 Claude 中打开 **Settings → Capabilities**，然后：
- 开启 **Code execution and file creation**；
- 开启 **Allow network egress**；
- 在 **Domain allowlist** 中添加 `platform.fatsecret.com` 和 `authentication.fatsecret.com`（或允许所有域名）。

**3. 安装技能**（只需一次）

1. 从 [Releases](../../releases/latest) 下载 `fatsecret-diary.zip`。
2. 在 Claude 中：**Settings → Capabilities → Skills → Upload skill**，选择该 zip 文件。

**4. 连接你的日记**（只需一次）

1. 在 Claude 中创建一个**项目（Project）**，例如"饮食日记"。
2. 在项目中新建对话，输入 *"连接我的 FatSecret"*。
3. Claude 会向你索取密钥，给你一个登录链接，并让你发回 FatSecret 显示的 PIN 码。
   - "Member name" 一栏请填写 FatSecret **用户名**，不是邮箱。
4. 最后 Claude 会显示一串**连接字符串**。
   - 把它以 `FatSecret: <字符串>` 的形式粘贴到**项目说明（project instructions）**中。
   - 之后该项目中的每个对话都能直接使用。

> ⚠️ 连接字符串可以访问你的日记，请不要分享给任何人。

### FatSecret 免费版的限制

- FatSecret 搜索只覆盖**美国数据库**（通用食物效果很好）。
- 本地品牌产品无法按名称搜索。请先在 **FatSecret 应用中记录一次**（例如扫描条形码），
  之后 Claude 就可以随时记录它。
- 无法通过 API 创建自定义食物。
- 每个密钥每天 5000 次 API 请求，个人使用完全足够。

### ChatGPT

ChatGPT 使用相同的技能格式，但目前 ChatGPT 的技能**无法访问互联网**，因此无法连接 FatSecret。
等 OpenAI 为技能开放网络访问后，这个技能应该也能在 ChatGPT 中使用。

### 隐私

- 该技能只与 FatSecret 通信。
- 你的密钥和令牌只保存在你的 Claude 项目和对话沙箱中。
- 不会发送到任何其他地方。

### 开发者

该技能是一个纯 Python 3.9+ 命令行工具，没有任何依赖。命令示例见上方英文部分的 "For developers"。

---

## Русский

Надоело вносить одну и ту же еду в десять разных мест? Этот скилл позволяет ИИ-ассистенту (Claude) вести ваш
дневник питания в [FatSecret](https://www.fatsecret.com). Просто пишете в чат:

> *«На завтрак овсянка 50 г и банан, кофе с молоком»*
> *«Обед как вчера»*
> *«Сколько белка я ела в среднем на этой неделе?»*
> *«Построй график веса и калорий за месяц»*

Claude записывает еду в **ваш собственный** дневник FatSecret. Дневник синхронизирован с приложением FatSecret
на телефоне, и всё можно анализировать в одном месте.

### Что умеет

- Записывать еду по тексту или фото (фото Claude сначала подтверждает с вами).
- Находить продукты: из вашей истории (любой страны и бренда) и простые продукты из базы FatSecret (яйца, рис, курица…).
- Править, удалять и переносить записи; копировать приём пищи или целый день; использовать сохранённые приёмы пищи.
- Записывать вес; смотреть и добавлять активность.
- Статистика: калории и БЖУ по дням, средние значения, динамика веса.
- Выгрузка в CSV и графики.

### Что понадобится

- **Аккаунт FatSecret** с ником и паролем. Если входите через Google или Apple, задайте пароль через
  «Забыли пароль?» на fatsecret.com.
- Аккаунт **Claude** (claude.ai).
- Около **15 минут** на разовую настройку.

### Настройка

**1. Получите бесплатные ключи разработчика FatSecret** (один раз)

1. Зарегистрируйтесь на https://platform.fatsecret.com/register. В поле «Business/Organization» можно написать «Personal use».
2. Войдите и откройте **My Account → API Key**.
3. В блоке **OAuth 1.0** скопируйте **Consumer Key** и **Consumer Secret**.
   - Не «Client Secret» от OAuth 2.0: он сюда не подходит.

**2. Разрешите Claude запускать код и обращаться к FatSecret** (один раз)

В Claude откройте **Settings → Capabilities** и:
- включите **Code execution and file creation**;
- включите **Allow network egress**;
- в **Domain allowlist** добавьте `platform.fatsecret.com` и `authentication.fatsecret.com` (или разрешите все домены).

**3. Установите скилл** (один раз)

1. Скачайте `fatsecret-diary.zip` из [Releases](../../releases/latest).
2. В Claude: **Settings → Capabilities → Skills → Upload skill** и выберите этот zip.

**4. Подключите дневник** (один раз)

1. Создайте в Claude **проект**, например «Дневник питания».
2. Начните в нём чат и напишите *«Подключи мой FatSecret»*.
3. Claude попросит ключи, даст ссылку для входа и попросит PIN, который покажет FatSecret.
   - В поле «Member name» вводите **ник** FatSecret, а не email.
4. В конце Claude покажет **строку подключения**.
   - Вставьте её в **инструкции проекта** в виде `FatSecret: <строка>`.
   - После этого любой чат в этом проекте сразу работает.

> ⚠️ Строка подключения даёт доступ к вашему дневнику. Никому её не показывайте.

### Ограничения бесплатного тарифа FatSecret

- Поиск FatSecret работает только по **базе США** (простые продукты находятся хорошо).
- Местные брендовые продукты по названию не найти. Внесите такой продукт **один раз в приложении FatSecret**
  (например, по штрихкоду), после этого Claude сможет записывать его когда угодно.
- Создавать свои продукты через API нельзя.
- 5000 запросов к API в день на ключ, для личного использования этого с запасом.

### ChatGPT

ChatGPT поддерживает тот же формат скиллов, но сейчас у скиллов ChatGPT **нет доступа в интернет**, поэтому
до FatSecret они не достучатся. Когда OpenAI откроет скиллам доступ в сеть, этот скилл должен заработать и там.

### Приватность

- Скилл общается только с FatSecret.
- Ключи и токен хранятся только в вашем проекте Claude и в «песочнице» чата.
- Больше никуда они не передаются.

### Для разработчиков

Скилл — это обычная CLI-программа на Python 3.9+ без зависимостей. Примеры команд — в английском разделе «For developers».

---

*Not affiliated with FatSecret. Nutrition data powered by the [fatsecret Platform API](https://platform.fatsecret.com).*
