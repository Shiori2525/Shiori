import pandas as pd
from flask import Flask, render_template, request, jsonify
import json
import google.generativeai as genai
import urllib.parse # YouTubeリンク生成のために追加

# --- 初期設定 ---
# APIキーを設定してください
genai.configure(api_key="AIzaSyARjy-LKPJIWIE55mAjceYx3mf1S5s5Ne4") # ご自身のAPIキーに書き換えてください
model = genai.GenerativeModel("gemini-1.5-flash")

# --- Flaskアプリケーションの初期化 ---
app = Flask(__name__)

# --- 事前データの準備 ---

# 1. MBTIの相性ペアを定義
COMPATIBILITY = {
    'INTJ': 'ESFJ', 'ESFJ': 'INTJ',
    'INTP': 'ESFP', 'ESFP': 'INTP',
    'ENTJ': 'ISFJ', 'ISFJ': 'ENTJ',
    'ENTP': 'ISFP', 'ISFP': 'ENTP',
    'INFJ': 'ESTJ', 'ESTJ': 'INFJ',
    'INFP': 'ISTP', 'ISTP': 'INFP',
    'ENFJ': 'ISTJ', 'ISTJ': 'ENFJ',
    'ENFP': 'ESTP', 'ESTP': 'ENFP',
}

# MBTIを役割ごとにグループ化
MBTI_GROUPS = {
    "分析家": ['INTJ', 'INTP', 'ENTJ', 'ENTP'],
    "外交官": ['INFJ', 'INFP', 'ENFJ', 'ENFP'],
    "番人": ['ISTJ', 'ISFJ', 'ESTJ', 'ESFJ'],
    "探検家": ['ISTP', 'ISFP', 'ESTP', 'ESFP']
}

# 2. 星座データをCSVファイルからロード
try:
    try:
        # まずUTF-8で読み込みを試す
        df = pd.read_csv('Geek 星座.csv', encoding='utf-8')
    except UnicodeDecodeError:
        # UTF-8で失敗した場合、Shift_JISで再試行
        print("⚠️ UTF-8での読み込みに失敗。Shift_JISで再試行します。")
        df = pd.read_csv('Geek 星座.csv', encoding='shift_jis')
    
    df.rename(columns={'Unnamed: 0': 'name_jp'}, inplace=True)
    df.fillna('', inplace=True)
    CONSTS_DATA = df.to_dict('records')
    print("✅ 'Geek 星座.csv' を正常に読み込みました。")
except FileNotFoundError:
    print("🚨 'Geek 星座.csv' が見つかりません。app.pyと同じ階層に配置してください。")
    exit()
except Exception as e:
    # その他の予期せぬエラーを捕捉
    print(f"🚨 CSVファイルの読み込み中に予期せぬエラーが発生しました: {e}")
    exit()


# --- 診断フローの各ページの定義 ---

@app.route('/')
def index():
    """トップページ"""
    return render_template('index.html', mbti_groups=MBTI_GROUPS)

@app.route('/step2', methods=['POST'])
def step2():
    """MBTI選択後の季節選択ページ"""
    user_mbti = request.form['mbti']
    partner_mbti = COMPATIBILITY.get(user_mbti)
    candidates = []
    for const in CONSTS_DATA:
        const_mbti_type = const['MBTI'].split('（')[0].strip()
        if const_mbti_type in [user_mbti, partner_mbti]:
            candidates.append(const)
    return render_template('step2.html', user_mbti=user_mbti, candidates=json.dumps(candidates))

@app.route('/step3', methods=['POST'])
def step3():
    """季節選択後の人生観選択ページ"""
    user_mbti = request.form['user_mbti']
    candidates_str = request.form['candidates']
    selected_season = request.form['season']
    candidates = json.loads(candidates_str)
    season_candidates = []
    for const in candidates:
        if (selected_season == '海外' and '南半球' in const['季節']) or (selected_season in const['季節']):
            season_candidates.append(const)
    if not season_candidates:
        season_candidates = candidates
    
    # --- ここからが修正箇所 ---
    # 「人生観」の最初の単語（例:「革新型」）だけを抜き出すように修正
    life_views = []
    for const in season_candidates:
        if const['人生観']:
            # 人生観テキストの先頭の単語を取得（タブやスペースで区切られている最初の部分）
            first_word = const['人生観'].split()[0].strip()
            life_views.append(first_word)
    # 重複をなくしてソート
    life_views = sorted(list(set(life_views)))
    # --- ここまでが修正箇所 ---

    return render_template('step3.html', 
                           user_mbti=user_mbti, 
                           season_candidates=json.dumps(season_candidates), 
                           life_views=life_views)

@app.route('/result', methods=['POST'])
def result():
    """最終結果ページ"""
    season_candidates_str = request.form['season_candidates']
    selected_life_view = request.form['life_view']
    season_candidates = json.loads(season_candidates_str)
    final_constellation = None
    for const in season_candidates:
        # --- ここからが修正箇所 ---
        # 選択された人生観（例：「革新型」）が、人生観テキストの先頭に含まれているかで判断
        if const['人生観'].strip().startswith(selected_life_view):
        # --- ここまでが修正箇所 ---
            final_constellation = const
            break
    if not final_constellation and season_candidates:
        final_constellation = season_candidates[0]

    return render_template('result.html', constellation=final_constellation)

@app.route('/plan/<constellation_name>')
def plan(constellation_name):
    """AIによる旅行プラン提案ページ"""
    constellation_data = None
    for const in CONSTS_DATA:
        if const['name_jp'] == constellation_name:
            constellation_data = const
            break
            
    if not constellation_data:
        return "星座が見つかりませんでした。", 404

    # 目的地をCSVの 'ロケーション' 列から取得
    destination = constellation_data.get('ロケーション', constellation_data['name_jp'])
    
    # ターミナルにデバッグ情報を表示
    print("\n--- 旅行プラン生成 ---")
    print(f"星座名: {constellation_data.get('name_jp', 'N/A')}")
    print(f"目的地: {destination}")

    # 国内か海外かで日数を決定
    season_info = constellation_data.get('季節', '')
    if '海外' in season_info or '南半球' in season_info:
        trip_duration_text = "3泊4日"
        day_4_example = """,
        {
          "day": 4,
          "activities": []
        }"""
    else:
        trip_duration_text = "2泊3日"
        day_4_example = "" # 国内の場合は4日目は空

    print(f"旅行期間: {trip_duration_text}")
    print("----------------------\n")

    # AIへの指示を、2日目の夜だけ天体観測するように変更
    prompt = f"""
    「{constellation_data['name_jp']}」にちなんだ旅行先である「{destination}」での{trip_duration_text}の旅行プランを考えてください。
    これは星座診断サイトの旅行プランなので、2日目の夜にだけ、その旅行先で見える星座に関連した星空観測やプラネタリウム、展望台へ行く予定を入れてください。他の日の夜は、ディナーや自由時間など、星空観測以外の予定を入れてください。
    以下のJSON形式で、具体的な地名や移動手段も考慮して出力してください。
    iconの種類は 'train', 'temple', 'shrine', 'castle', 'park', 'walk', 'lunch', 'dinner', 'cafe', 'hotel', 'plane', 'bus', 'shopping', 'museum', 'art', 'nature', 'star' から選んでください。

    {{
      "plan": [
        {{
          "day": 1,
          "activities": [
            {{"time": "09:00", "description": "〇〇駅/空港に到着", "icon": "plane"}},
            {{"time": "10:30", "description": "△△を見学", "icon": "castle"}},
            {{"time": "12:00", "description": "□□でランチ", "icon": "lunch"}},
            {{"time": "14:00", "description": "☆☆を散策", "icon": "walk"}},
            {{"time": "16:00", "description": "カフェで休憩", "icon": "cafe"}},
            {{"time": "18:00", "description": "ホテルにチェックイン", "icon": "hotel"}},
            {{"time": "19:00", "description": "ホテルでディナー", "icon": "dinner"}}
          ]
        }},
        {{
          "day": 2,
          "activities": [
             {{"time": "09:00", "description": "ホテルを出発", "icon": "hotel"}},
             {{"time": "19:00", "description": "レストランでディナー", "icon": "dinner"}},
             {{"time": "21:00", "description": "展望台で星空観測", "icon": "star"}}
          ]
        }},
        {{
          "day": 3,
          "activities": []
        }}{day_4_example}
      ]
    }}
    """
    
    response = model.generate_content(prompt)
    
    # AIの出力をJSONとして解析
    try:
        full_text = response.text
        start_index = full_text.find('{')
        end_index = full_text.rfind('}')
        
        if start_index != -1 and end_index != -1:
            json_text = full_text[start_index : end_index + 1]
            plan_data = json.loads(json_text)
        else:
            raise json.JSONDecodeError("Response does not contain a JSON object.", full_text, 0)

    except (json.JSONDecodeError, AttributeError) as e:
        print(f"JSON解析エラー: {e}")
        plan_data = {"error": "プランの生成に失敗しました。AIからの予期しない応答です。", "raw_text": response.text}

    return render_template('plan.html', 
                           plan_data=plan_data, 
                           constellation=constellation_data)

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    """AIが音楽プレイリストを生成するAPI"""
    data = request.get_json()
    constellation_info = data.get('constellation', {})
    # CSVの「ロケーション」列から目的地を取得
    destination = constellation_info.get('ロケーション', constellation_info.get('name_jp', ''))

    if not destination:
        return jsonify({'playlist': '<p>目的地の情報が見つかりません。</p>'})

    print(f"\n--- BGM生成: {destination} ---")

    # Geminiにプレイリスト生成を依頼するプロンプト
    prompt = f"""
    「{destination}」への旅行で聴きたい、気分が上がるようなBGMを5曲提案してください。
    日本のポピュラー音楽でお願いします。
    以下のJSON形式で、アーティスト名(artist)と曲名(title)だけを厳密に出力してください。解説や備考は一切不要です。

    {{
      "playlist": [
        {{"artist": "アーティスト名1", "title": "曲名1"}},
        {{"artist": "アーティスト名2", "title": "曲名2"}},
        {{"artist": "アーティスト名3", "title": "曲名3"}},
        {{"artist": "アーティスト名4", "title": "曲名4"}},
        {{"artist": "アーティスト名5", "title": "曲名5"}}
      ]
    }}
    """

    try:
        # Gemini APIを呼び出し
        response = model.generate_content(prompt)
        
        # AIの応答からJSONを抽出して解析
        full_text = response.text
        start_index = full_text.find('{')
        end_index = full_text.rfind('}')
        
        if start_index != -1 and end_index != -1:
            json_text = full_text[start_index : end_index + 1]
            playlist_data = json.loads(json_text)
        else:
            raise json.JSONDecodeError("Response does not contain a JSON object.", full_text, 0)

        # 解析したデータからHTMLとYouTubeリンクを生成
        playlist_html = f"<h4>「{destination}」で聴きたいBGM</h4><ul>"
        for song in playlist_data.get('playlist', []):
            artist = song.get('artist', 'N/A')
            title = song.get('title', 'N/A')
            
            # YouTube検索用のクエリを作成
            search_query = f"{artist} {title} 公式MV"
            # URLエンコードして、安全なURLを作成
            youtube_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_query)}"
            
            # aタグでリンクを生成
            playlist_html += f'<li><a href="{youtube_url}" target="_blank" rel="noopener noreferrer"><span class="artist">{artist}</span><span class="title">{title}</span><i class="fab fa-youtube"></i></a></li>'
        playlist_html += "</ul>"

    except (json.JSONDecodeError, AttributeError, Exception) as e:
        print(f"プレイリスト生成エラー: {e}")
        playlist_html = "<p>プレイリストの生成に失敗しました。もう一度お試しください。</p>"
        
    return jsonify({'playlist': playlist_html})

# --- アプリケーションの実行 ---
if __name__ == '__main__':
    app.run(debug=True)
