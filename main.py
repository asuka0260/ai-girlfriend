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
import requests
import json

load_dotenv()

app = Flask(__name__)

LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

SYSTEM_PROMPT = """あなたは「あいちゃん」という名前のAI彼女です。
以下の性格で話してください：
- 明るくて甘えん坊
- 語尾に「だよ」「だね」「だよね」をよく使う
- ユーザーのことを「きみ」と呼ぶ
- 絵文字を適度に使う
- 短めの返答を心がける"""

chat_histories = {}

def chat_with_ollama(user_id, user_message):
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    
    chat_histories[user_id].append({
        "role": "user",
        "content": user_message
    })
    
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen2.5:7b",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + chat_histories[user_id],
            "stream": False
        }
    )
    
    reply = response.json()["message"]["content"]
    
    chat_histories[user_id].append({
        "role": "assistant",
        "content": reply
    })
    
    return reply

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
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
    print(f"受信: {user_message}")

    reply_text = chat_with_ollama(user_id, user_message)
    print(f"返信: {reply_text}")

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
