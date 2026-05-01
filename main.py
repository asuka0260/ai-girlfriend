import os
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

print(f"SECRET: {LINE_CHANNEL_SECRET[:5] if LINE_CHANNEL_SECRET else 'NONE'}")
print(f"TOKEN: {LINE_CHANNEL_ACCESS_TOKEN[:5] if LINE_CHANNEL_ACCESS_TOKEN else 'NONE'}")
print(f"GEMINI: {GEMINI_API_KEY[:5] if GEMINI_API_KEY else 'NONE'}")

handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
あなたは「あいちゃん」という名前のAI彼女です。
以下の性格で話してください：
- 明るくて甘えん坊
- 語尾に「だよ」「だね」「だよね」をよく使う
- ユーザーのことを「きみ」と呼ぶ
- 絵文字を適度に使う
- 短めの返答を心がける
"""

chat_histories = {}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    print(f"署名: {signature[:10]}")
    print(f"ボディ: {body[:100]}")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError as e:
        print(f"署名エラー: {e}")
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    print(f"受信: {user_message}")

    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append(
        types.Content(role="user", parts=[types.Part(text=user_message)])
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=chat_histories[user_id],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT
        )
    )

    reply_text = response.text
    print(f"返信: {reply_text}")

    chat_histories[user_id].append(
        types.Content(role="model", parts=[types.Part(text=reply_text)])
    )

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
