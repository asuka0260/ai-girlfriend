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

handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET"))
configuration = Configuration(
    access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
)

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

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
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    if user_id not in chat_histories:
        chat_histories[user_id] = []

    chat_histories[user_id].append(
        types.Content(role="user", parts=[types.Part(text=user_message)])
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=chat_histories[user_id],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT
        )
    )

    reply_text = response.text

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
