# Basic Introduction to Webhooks

A webhook is a way for one application to automatically notify another application when something happens.

Instead of your app repeatedly asking, "Is there anything new?", the other service sends a request to your app as soon as there is an update.

For a Telegram bot, a webhook means:

1. A user sends a message to your bot.
2. Telegram receives the message.
3. Telegram sends the message data to your server URL using an HTTPS POST request.
4. Your server handles the message and can reply using the Telegram Bot API.

This is different from polling, where your app keeps calling Telegram's `getUpdates` method to ask for new messages.

## Telegram BotFather Example

BotFather is used to create and manage Telegram bots. It gives you a bot token, which is required when calling the Telegram Bot API.

### 1. Create a Bot and Get the Token

1. Open Telegram.
2. Search for `@BotFather`.
3. Start a chat with BotFather.
4. Send:

```text
/newbot
```

5. Follow the instructions.
6. Copy the bot token BotFather gives you.

The token usually looks similar to this:

```text
123456789:ABCdefYourBotTokenHere
```

Keep this token private. Anyone with the token can control your bot.

## Create a Webhook Manually

Before creating a webhook, you need a public HTTPS URL that Telegram can reach. If the server is deployed on Render, the URL usually looks like:

Example Render webhook URL:

```text
https://<RENDER_SERVICE_NAME>.onrender.com/telegram/webhook
```

To set the webhook manually, run:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<WEBHOOK_URL>"
```

Example:

```bash
curl "https://api.telegram.org/bot123456789:ABCdefYourBotTokenHere/setWebhook?url=https://my-telegram-bot.onrender.com/telegram/webhook"
```

If successful, Telegram returns a response similar to:

```json
{
  "ok": true,
  "result": true,
  "description": "Webhook was set"
}
```

## Check the Current Webhook

To check whether a webhook is currently set:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

Example:

```bash
curl "https://api.telegram.org/bot123456789:ABCdefYourBotTokenHere/getWebhookInfo"
```

This shows the current webhook URL, pending updates, and recent delivery errors if any exist.

## Delete a Webhook Manually

If you want to remove the webhook and switch back to polling with `getUpdates`, run:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook"
```

Example:

```bash
curl "https://api.telegram.org/bot123456789:ABCdefYourBotTokenHere/deleteWebhook"
```

If you also want Telegram to drop pending updates that were not delivered yet:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/deleteWebhook?drop_pending_updates=true"
```

## Important Notes

- Telegram webhooks require a public HTTPS endpoint.
- Do not share your bot token in public code, screenshots, or logs.
- A bot cannot use webhook delivery and `getUpdates` polling at the same time.
- Use `getWebhookInfo` when debugging webhook problems.
- Your webhook route should accept POST requests from Telegram.

## Flask App Configuration

The Flask app in `app.py` uses Gemini with chat memory and Google Search grounding. It also exposes a Telegram webhook endpoint.

Adjust the Gemini model, system prompt, and webhook URL in `config.yml`:

```yaml
gemini:
  model: gemini-2.5-flash
  system_prompt: you are helpful assistant

webhook:
  base_url: https://<RENDER_SERVICE_NAME>.onrender.com
  path: /telegram/webhook
```

Keep secrets in environment variables, not in `config.yml`. Set these environment variables on Render:

```text
GEMINI_API_KEY=your_gemini_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

Optional environment variables can override `config.yml`:

```text
GEMINI_MODEL=gemini-2.5-flash
SYSTEM_PROMPT=you are helpful assistant
WEBHOOK_BASE_URL=https://<RENDER_SERVICE_NAME>.onrender.com
WEBHOOK_PATH=/telegram/webhook
CONFIG_PATH=config.yml
```

Render start command:

```bash
gunicorn app:app
```

The app provides:

- `GET /` for a health check.
- `POST /chat` for direct API chat requests.
- `POST /telegram/webhook` for Telegram webhook updates.

## How the Flask App Works

When the app starts, it first reads `config.yml` and environment variables. The YAML file stores easy-to-change settings like the Gemini model, system prompt, and webhook URL. Environment variables store private values like `GEMINI_API_KEY` and `TELEGRAM_BOT_TOKEN`.

The app then creates a Gemini client and configures it with:

- A system prompt from `config.yml`.
- Google Search grounding.
- A chat session per `session_id` or Telegram chat ID, stored in memory.

The basic flow for `POST /chat` is:

1. A user sends JSON with a `message`.
2. Flask reads the message and `session_id`.
3. The app finds or creates a Gemini chat session for that `session_id`.
4. Gemini receives the message with previous chat context.
5. Flask returns Gemini's reply as JSON.

The basic flow for Telegram is:

1. A Telegram user sends a message to the bot.
2. Telegram sends the update to `/telegram/webhook`.
3. Flask extracts the chat ID and text.
4. The app sends the text to Gemini using the Telegram chat ID as memory.
5. The app sends Gemini's reply back to the user through Telegram.

## Why Delete the Webhook on Startup?

On startup, the app deletes the existing Telegram webhook with `drop_pending_updates=true`, then sets the webhook again.

This helps during tutorials and redeployments because Telegram may have old undelivered messages waiting in its queue. If those pending updates are not dropped, Telegram can send old messages to the newly deployed app as soon as the webhook is restored. That can make the bot reply to stale messages and confuse testing.

Resetting the webhook gives the app a clean start:

1. Remove the old webhook.
2. Drop pending updates.
3. Set the webhook again using the current Render URL.

For production apps, you may choose not to drop pending updates if every message must be processed.

Example direct chat request:

```bash
curl -X POST "https://<RENDER_SERVICE_NAME>.onrender.com/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","message":"I am building a data pipeline with Meltano."}'
```
