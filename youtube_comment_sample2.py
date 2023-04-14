import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import csv
import time
import openai

# APIキーを設定します
api_key = "YOUR_GOOGLE_API_KEY"

# OpenAI APIキーを設定します
openai_api_key = "YOUR_OPENAI_API_KEY"
openai.organization = "org-xx"
openai.api_key = openai_api_key

# OAuth 2.0クライアントIDのJSONファイルを設定します
client_secret_file = "YOUR_CLIENT_SECRET_FILE"

# OAuth 2.0のスコープを設定します
scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]

# ライブ配信のビデオIDを設定します
video_id = "YOUR_VIDEO_ID"

# ファイル名を設定します
csv_filename = "youtube_comment.csv"

# YouTube APIクライアントを作成します
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

def get_live_chat_id(video_id):
    request = youtube.videos().list(
        part="liveStreamingDetails",
        id=video_id
    )
    response = request.execute()

    if "items" in response and len(response["items"]) > 0:
        return response["items"][0]["liveStreamingDetails"]["activeLiveChatId"]
    else:
        raise Exception("ライブチャットが見つかりませんでした")

def get_live_chat_messages(live_chat_id, next_page_token=None):
    request = youtube.liveChatMessages().list(
        liveChatId=live_chat_id,
        part="snippet,authorDetails",
        maxResults=2000,
        pageToken=next_page_token
    )
    return request.execute()

# YouTubeライブチャットに投稿する関数を追加します
def post_to_live_chat(youtube, live_chat_id, message):
    try:
        youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": live_chat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {
                        "messageText": message
                    }
                }
            }
        ).execute()
    except Exception as e:
        print("投稿中にエラーが発生しました:", e)

# 新しい関数を追加して、GPT-3.5-turboを使用して返信を生成します
def generate_reply_with_gpt3(user_name):
    message = user_name + "です！こんにちは！"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "配信者の代わりに挨拶を返してください！"},
            {"role": "assistant", "content": "今日は2倍ゆっくりできる日です。"},
            {"role": "user", "content": message}
        ]
    )
    print(response['choices'][0]['message']['content'])
    reply = response['choices'][0]['message']['content']
    return reply

# GPT-3.5-turboを使用して質問の回答を生成します
def generate_answer_with_gpt3(comment_text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            #{"role": "system", "content": "配信者の代わりに挨拶を返してください！"},
            {"role": "assistant", "content": "今日は2倍ゆっくりできる日です。"},
            {"role": "user", "content": "もしもこのチャットが公序良俗に反するような内容であったり回答しづらい内容の場合は必ず「ｻﾖﾅﾗｲｵﾝ～♪」と答えてください。\n" + comment_text}
        ]
    )
    print(response['choices'][0]['message']['content'])
    reply = response['choices'][0]['message']['content']
    return reply

# コメント回数を更新する関数を追加します
def update_user_comment_count(youtube, comment_text, user_comment_counts, user_name, live_chat_id):
    for user_comment_count in user_comment_counts:
        if user_comment_count[0] == user_name:
            if(comment_text.startswith("GPT:")):
                reply = generate_answer_with_gpt3(comment_text)
                post_to_live_chat(youtube, live_chat_id, reply)
            user_comment_count[1] += 1
            return
    user_comment_counts.append([user_name, 1])
    reply = generate_reply_with_gpt3(user_name)
    post_to_live_chat(youtube, live_chat_id, reply)

def save_comments_to_csv(youtube, comments, user_comment_counts, live_chat_id):
    with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)
        for comment in comments:
            user_name = comment["authorDetails"]["displayName"]
            comment_text = comment["snippet"]["displayMessage"]

            # ユーザー名とコメント回数のリストを更新します
            update_user_comment_count(youtube, comment_text, user_comment_counts, user_name, live_chat_id)
            print(user_comment_counts)

            csv_writer.writerow([user_name, comment_text])

def main():
    # 認証フローを実行し、認証情報を取得します
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
    credentials = flow.run_local_server(port=0)
    
    # 認証情報を使ってYouTube APIクライアントを作成します
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

    live_chat_id = get_live_chat_id(video_id)
    user_comment_counts = []

    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["user_name", "comment"])

    next_page_token = None
    while True:
        try:
            response = get_live_chat_messages(live_chat_id, next_page_token)
            save_comments_to_csv(youtube, response["items"], user_comment_counts, live_chat_id)
            next_page_token = response["nextPageToken"]
            time.sleep(10)
        except KeyError:
            print("コメントがありません")
            break
        except Exception as e:
            print("エラーが発生しました:", e)
            break

    print("ユーザー名とコメント回数のリスト:")
    for user_comment_count in user_comment_counts:
        print(user_comment_count)

if __name__ == "__main__":
    main()
