import os
import datetime
import feedparser
from google import genai
from google.cloud import texttospeech
from email.utils import formatdate

# .env を読み込む
from dotenv import load_dotenv
load_dotenv()

# --- 設定 ---
RSS_URL = "https://b.hatena.ne.jp/hotentry/it.rss"
MAX_NEWS_COUNT = 5 # 取得するニュースの件数
AUDIO_DIR = "docs/audio"
ARCHIVE_FILE = "docs/index.md"
# GITHUB_PAGES_URL = "https://[あなたのユーザー名].github.io/[リポジトリ名]/"

def fetch_news():
    """はてブITカテゴリーから最新ニュースを取得"""
    feed = feedparser.parse(RSS_URL)
    news_list = []
    for entry in feed.entries[:MAX_NEWS_COUNT]:
        news_list.append({
            'title': entry.title,
            'summary': entry.summary if 'summary' in entry else entry.title,
            'url': entry.link
        })
    return news_list

def generate_script(news_list):
    """Gemini APIでラジオ原稿を作成"""
    client = genai.Client() # 環境変数 GEMINI_API_KEY を自動認識
    
    news_text = ""
    for idx, news in enumerate(news_list, 1):
        news_text += f"{idx}. タイトル: {news['title']}\n   概要: {news['summary']}\n\n"
        
    prompt = f"""
    あなたは朝のITニュース番組のアナウンサーです。
    以下のニュースリストから、通勤中に聴くための自然なラジオ原稿を作成してください。
    
    【条件】
    ・「おはようございます、本日のITトレンドをお伝えします」から始めること。
    ・箇条書きは使わず、自然な話し言葉（です・ます調）にすること。
    ・全体で約3分（約900〜1000文字）でまとめること。
    ・最後に「今日も一日頑張りましょう」と締めること。
    
    【ニュース】
    {news_text}
    """
    
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt
    )
    return response.text

def generate_audio(script_text, filename):
    """Google Cloud TTSで音声を生成"""
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=script_text)
    
    # アナウンサー風の落ち着いた男性の声（Neural2-B）を指定
    voice = texttospeech.VoiceSelectionParams(
        language_code="ja-JP",
        name="ja-JP-Neural2-B" 
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    
    filepath = os.path.join(AUDIO_DIR, filename)
    with open(filepath, "wb") as out:
        out.write(response.audio_content)
    return filepath

def update_archive(news_list, today_str):
    """アーカイブ(index.md)の更新"""
    new_content = f"## {today_str}のニュース\n\n"
    for news in news_list:
        new_content += f"- [{news['title']}]({news['url']})\n"
    new_content += "\n---\n\n"
    
    existing_content = ""
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
            existing_content = f.read()
            
    with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
        f.write(new_content + existing_content)

def update_rss(news_list, mp3_filename, today_str):
    """ポッドキャスト用RSS(feed.xml)の生成とShow Notesの追加"""
    rss_file = "docs/feed.xml"
    
    # ★ ここは後でGitHubにアップロードする際に書き換えます
    base_url = "https://[あなたのユーザー名].github.io/daily-podcast/" 
    audio_url = f"{base_url}audio/{mp3_filename}"
    
    # アプリの詳細欄(Show Notes)に表示するHTMLリンクを作成
    show_notes = f"<h2>{today_str}のニュース引用元</h2><ul>"
    for news in news_list:
        show_notes += f'<li><a href="{news["url"]}">{news["title"]}</a></li>'
    show_notes += "</ul>"
    
    # 現在の時刻をポッドキャスト用の形式で取得
    pub_date = formatdate(localtime=False)
    
    # XMLのテンプレートに流し込む
    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>毎朝のITトレンド</title>
    <description>最新のITニュースを自動でお届けします。</description>
    <link>{base_url}</link>
    <language>ja</language>
    <item>
      <title>{today_str}のニュース</title>
      <description><![CDATA[{show_notes}]]></description>
      <enclosure url="{audio_url}" type="audio/mpeg" />
      <pubDate>{pub_date}</pubDate>
      <guid>{audio_url}</guid>
    </item>
  </channel>
</rss>"""
    
    with open(rss_file, "w", encoding="utf-8") as f:
        f.write(rss_content)

def main():
    today_str = datetime.datetime.now().strftime("%Y年%m月%d日")
    mp3_filename = f"episode_{datetime.datetime.now().strftime('%Y%m%d')}.mp3"
    
    # docs/audio フォルダがなければ作成
    os.makedirs(AUDIO_DIR, exist_ok=True)

    print("1. はてブからニュースを取得中...")
    news_list = fetch_news()

    print("2. Geminiで原稿を作成中...")
    script = generate_script(news_list)
    print("【生成された原稿】\n", script[:100], "...\n")

    print("3. Google Cloud TTSで音声化中...")
    generate_audio(script, mp3_filename)

    print("4. アーカイブ(Markdown)を更新中...")
    update_archive(news_list, today_str)
    
    print("5. ポッドキャスト用RSSを生成中...")
    update_rss(news_list, mp3_filename, today_str)

    print("すべての処理が完了しました！")

if __name__ == "__main__":
    main()