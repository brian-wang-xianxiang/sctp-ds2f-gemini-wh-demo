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
https://<RENDER_SERVICE_NAME>.onrender.com/telegram_webhook
```

To set the webhook manually, run:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<WEBHOOK_URL>"
```

Example:

```bash
curl "https://api.telegram.org/bot123456789:ABCdefYourBotTokenHere/setWebhook?url=https://my-telegram-bot.onrender.com/telegram_webhook"
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
  path: /telegram_webhook
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
WEBHOOK_PATH=/telegram_webhook
CONFIG_PATH=config.yml
```

Render start command:

```bash
gunicorn app:app
```

The app provides:

- `GET /` to show the current webhook information.
- `POST /telegram_webhook` for Telegram webhook updates.

## How the Flask App Works

When the app starts, it first reads `config.yml` and environment variables. The YAML file stores easy-to-change settings like the Gemini model, system prompt, and webhook URL. Environment variables store private values like `GEMINI_API_KEY` and `TELEGRAM_BOT_TOKEN`.

The app then creates a Gemini client and configures it with:

- A system prompt from `config.yml`.
- Google Search grounding.
- A chat session per `session_id` or Telegram chat ID, stored in memory.

The basic flow for `/telegram_webhook` is:

1. A Telegram user sends a message to the bot.
2. Telegram sends the update to `/telegram_webhook`.
3. Flask extracts the chat ID and text.
4. The app sends the text to Gemini using the Telegram chat ID as memory.
5. The app sends Gemini's reply back to the user through Telegram.

The `/` route is only for checking the app. It returns information such as the configured Gemini model, webhook path, and webhook URL.

## Basic Gemini API Usage with Memory and Google Search

This app uses the Gemini API through the `google-genai` Python package. The important Gemini setup is:

```python
from google import genai
from google.genai import types

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

gemini_config = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=[types.Tool(google_search=types.GoogleSearch())],
)
```

The `system_instruction` field is the system prompt from `config.yml`. This is where you define the assistant's behavior:

```yaml
gemini:
  system_prompt: you are helpful assistant
```

The `tools` field enables Google Search grounding:

```python
tools=[types.Tool(google_search=types.GoogleSearch())]
```

This lets Gemini use Google Search when it needs current or external information, such as recent events, prices, schedules, or facts that may have changed.

The app creates one Gemini chat session per Telegram chat:

```python
chats = {}

def get_or_create_chat(session_id):
    if session_id not in chats:
        chats[session_id] = gemini_client.chats.create(
            model=MODEL_ID,
            config=gemini_config,
        )

    return chats[session_id]
```

When a Telegram message arrives, the app uses the Telegram chat ID as the memory key:

```python
gemini_chat = get_or_create_chat(f"telegram:{chat_id}")
gemini_response = gemini_chat.send_message(text)
reply = gemini_response.text or ""
```

The `text` value is the user's latest Telegram message. Because the app reuses the same `gemini_chat` object for the same Telegram chat ID, Gemini can understand earlier messages in that same conversation.

A very small standalone Gemini example looks like this:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_GEMINI_API_KEY")

config = types.GenerateContentConfig(
    system_instruction="You are a helpful assistant.",
    tools=[types.Tool(google_search=types.GoogleSearch())],
)

chat = client.chats.create(
    model="gemini-2.5-flash",
    config=config,
)

response = chat.send_message("What is Python?")
print(response.text)

response = chat.send_message("Explain that in one sentence.")
print(response.text)
```

The second message can say "that" because it uses the same chat session.

## Gemini Memory Limitations

The memory in this tutorial is intentionally simple.

The app stores Gemini chat sessions in this Python dictionary:

```python
chats = {}
```

This means:

- Memory is kept only while the server process is running.
- Memory is lost when the app restarts, redeploys, crashes, or scales to a different server instance.
- Memory is separate for each Telegram chat ID.
- The app stores Gemini chat session objects in memory, not a permanent transcript.
- If the app runs with multiple workers, each worker has its own separate `chats` dictionary.
- Longer conversations still have context limits. Very long chats may eventually need summarizing or trimming.
- Previous conversation context can increase token usage because earlier context may be included when Gemini responds.
- Google Search grounding may add latency when Gemini decides search is useful.

This setup is good for a tutorial because it keeps the code short. For production, use persistent storage.

## Adding Persistent Chat History Later

To keep memory after restarts, store chat history in a database instead of only using the `chats` dictionary.

A simple database table can look like this:

```text
telegram_chat_id
role
message_text
created_at
```

Then save each user message and assistant reply:

```text
telegram_chat_id | role      | message_text
12345            | user      | What is Python?
12345            | model     | Python is a programming language...
```

The flow becomes:

1. Telegram sends a message.
2. Look up recent messages by `telegram_chat_id` in the database.
3. Rebuild the recent conversation history for Gemini.
4. Send the new user message to Gemini.
5. Save the user message to the database.
6. Save Gemini's reply to the database.
7. Send Gemini's reply back to Telegram.

The basic idea looks like this:

```python
def handle_message(telegram_chat_id, user_text):
    history = load_recent_messages(telegram_chat_id, limit=20)

    contents = []
    for item in history:
        contents.append(
            types.Content(
                role=item["role"],
                parts=[types.Part(text=item["message_text"])],
            )
        )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=user_text)],
        )
    )

    response = gemini_client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=gemini_config,
    )

    save_message(telegram_chat_id, "user", user_text)
    save_message(telegram_chat_id, "model", response.text)

    return response.text or ""
```

For a small project, SQLite is enough. For a deployed app, use a managed database such as PostgreSQL, Redis, Firestore, or another storage service available on your hosting platform.

For long-running bots, do not load every message forever. Load only the most recent messages, or store a running summary of older messages and combine that summary with the latest conversation turns. This keeps requests smaller and reduces the chance of exceeding the model's context limit.

Keep privacy in mind. If you store user messages, tell users what you store and protect the database.

## Why Delete the Webhook on Startup?

On startup, the app deletes the existing Telegram webhook with `drop_pending_updates=true`, then sets the webhook again.

This helps during tutorials and redeployments because Telegram may have old undelivered messages waiting in its queue. If those pending updates are not dropped, Telegram can send old messages to the newly deployed app as soon as the webhook is restored. That can make the bot reply to stale messages and confuse testing.

Resetting the webhook gives the app a clean start:

1. Remove the old webhook.
2. Drop pending updates.
3. Set the webhook again using the current Render URL.

For production apps, you may choose not to drop pending updates if every message must be processed.

Example webhook info request:

```bash
curl "https://<RENDER_SERVICE_NAME>.onrender.com/"
```
