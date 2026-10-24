"""Build localization/en/koubai.json (shop text) from the decoded Japanese in
localization/work/koubai_strings.json, using templates for the repeated
ending / memory / album descriptions. Lines stay within 20 cells.

Usage: python make_koubai_en.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(REPO, "localization", "work", "koubai_strings.json")
DST = os.path.join(REPO, "localization", "en", "koubai.json")
WIDTH = 20

NAMES = {"バツ": "Batsu", "ひなた": "Hinata", "恭介": "Kyosuke", "将馬": "Shoma", "夏": "Natsu",
         "ロベルト": "Roberto", "ロイ": "Roy", "ティファニー": "Tiffany", "ボーマン": "Boman",
         "エッジ": "Edge", "岩": "Gan", "アキラ": "Akira", "素顔あきら": "Akira unmasked",
         "あきら": "Akira", "醍醐": "Daigo", "英雄": "Hideo", "響子": "Kyoko", "雷蔵": "Raizo",
         "霞": "Kasumi", "熱血隼人": "Hayato", "さくら": "Sakura", "流": "Nagare", "ラン": "Ran",
         "EDITキャラ": "EDIT char"}

FIXED = {
    "ジャスティス学園キャラのイラストが\n見られるトレーディングカードです\n中身は買ってのお楽しみ!":
        "Trading cards with\nJustice High art\nWhat you get is a\nsurprise!",
    "ジャスティス学園キャラのイラストが\n見られる熱血カードの10枚セットです\n1枚ずつ買うよりちょっとお得です":
        "A set of 10 cards of\nJustice High art\nCheaper than buying\nthem one at a time",
    "ゲーム中に演奏されるBGMが間ける\nジャスティス学園サウンドトラックCDです":
        "The Justice High\nsoundtrack CD with\nthe game music",
    "アーケード版ジャスティス学園の販促用\nポスターです":
        "Promo poster for the\narcade Justice High",
    "ジャスティス学園ムック表紙用の\nイラストです":
        "Cover art of the\nJustice High\nfan book",
    "プレイステーション版ジャスティス学園の\nパッケージイラストです":
        "Box art of Justice\nHigh on PlayStation",
    "ジャスティス学園ドラマアルバムの\nパッケージイラストです":
        "Cover art of the\nJustice High\ndrama CD",
    "ポケットステーション用のミニゲームです\nポケットステーションを持っていれば\n遊ぶことができます":
        "A PocketStation\nminigame you can\nplay if you own one",
    "このアイテムを買うと、ローディング画面\nのイラストを見られるようになります":
        "Unlocks the art\nshown on loading\nscreens",
    "スタッフロールが見れるようになります": "Unlocks the\nstaff roll",
    "この品物は売りきれました": "Sold out",
    "この品物の入荷は末定です": "Not in stock yet",
    "熱血カード": "Nekketsu Card",
    "熱血カード{99,99,99}10枚": "10 Cards",
    "ひなた{99,99,99}体操着": "Hinata Gym",
    "ティファニー{99,99,99}制服": "Tiffany Uniform",
    "J学サントラCD": "JH Soundtrack",
    "熱血イラスト集": "Art Gallery",
    "スタッフロール": "Staff Roll",
    "ポケジャス": "PocketJustice",
    "クリスマスの思い出": "Christmas",
    "ー売り切れー": "-Sold Out-",
    "ー入荷末定ー": "-Coming Soon-",
    # Girl at the counter
    "いらっしゃいませ\n何か欲しいものがあるのかしら?": "Welcome! Is there\nanything you want?",
    "お買い上げありがとうございます": "Thanks for buying!",
    "あら?\nポイントが足りないみたいね": "Oh? You seem to be\nshort of points",
    "まいどありがとうございました\nまたのご来店をお待ちしております": "Thank you very much!\nPlease come again!",
    # Boy at the counter
    "おや、いらっしゃい\n今日は珍しいものがそろってるよ": "Oh, welcome!\nGot rare stuff today",
    "はい、まいど": "Here you go!",
    "おや、ポイントが足りないみたいだよ\n残念だねえ": "Oh, you are short\non points Too bad",
    "また欲しいものがあったら、\nいつでもおいで": "If you want anything\nelse, come any time",
}
# Yes/No prompts keep "はい" at cell 5 and "いいえ" at cell 13 (cursor positions).
YESNO = "     Yes     No     "
PROMPTS = {"これを買うのね?": "You want this one?", "あら、もう帰るの?": "Leaving already?",
           "これを買うんだね?": "So you want this?"}

S = r"\{99,99,99\}"


def translate(ja):
    if ja in FIXED:
        return FIXED[ja]
    m = re.fullmatch(r"(.+)\n\n(" + S + r")+はい(" + S + r")+いいえ(" + S + r")+", ja)
    if m and m.group(1) in PROMPTS:
        return PROMPTS[m.group(1)] + "\n\n" + YESNO
    m = re.fullmatch(r"「一人で遊ぶ」モードの(.+)の\n(グッド|バッド)エンディングがいつでも見れるように\nなります", ja)
    if m:
        kind = "good" if m.group(2) == "グッド" else "bad"
        return "%s\nArcade %s ending\nany time" % (NAMES[m.group(1)], kind)
    m = re.fullmatch(r"「熱血青春日記」での(.+)との\n思い出がいつでも見れるようになります", ja)
    if m:
        return "%s: Youth Diary\nmemories, any time" % NAMES[m.group(1)]
    m = re.fullmatch(r"隠しキャラの「(.+)」\nが使えるようになります", ja)
    if m:
        who = {"体操着を着たひなた": "Hinata in\nher gym clothes", "制服を着た夏": "Natsu in\nher school uniform",
               "制服姿のティファニー": "Tiffany in\nher school uniform",
               "私服姿の響子先生": "Ms Kyoko in\nher casual clothes"}[m.group(1)]
        return "Unlocks secret char\n" + who
    m = re.fullmatch(r"ランちゃんの.+蔵コレクションです\n(.+)\nいつでも見れるようになります", ja)
    if m:
        album = {"クラブ{3,5,0}当の人のアルバムが": "club album",
                 "夏に{3,6,0}ったみんなのアルバムを": "summer album",
                 "クリスマスの時のアルバムが": "Xmas album"}[m.group(1)]
        return "From Ran's private\ncollection: the\n%s\nany time" % album
    m = re.fullmatch(r"(お買い上げありがとうございます|はい、まいど)\nキャラクターセレクトで「(.+)」に\n"
                     r"カーソルをあわせてSTARTボタンを\nおすと使えるようになる(わよ|からね)", ja)
    if m:
        lead = "Thanks for buying!" if m.group(1).startswith("お") else "Here you go!"
        return "%s\nOn Character Select\npick %s, press\nSTART to play" % (lead, NAMES[m.group(2)])
    m = re.fullmatch(r"(.+?)(?:" + S + r")?(ED1|ED2|日記)", ja)
    if m and m.group(1) in NAMES:
        return "%s %s" % (NAMES[m.group(1)], {"日記": "Diary"}.get(m.group(2), m.group(2)))
    m = re.fullmatch(r"熱血ポスター(\d)", ja)
    if m:
        return "Poster " + m.group(1)
    m = re.fullmatch(r"クラブ\{3,0,0\}介" + S + r"(\d)", ja)
    if m:
        return "Club Album " + m.group(1)
    m = re.fullmatch(r"夏の日の思い出" + S + r"(\d)", ja)
    if m:
        return "Summer Days " + m.group(1)
    return None


src = json.load(open(SRC, encoding="utf-8"))
out, missing, too_long = {}, [], set()
for addr, v in src.items():
    en = translate(v["ja"])
    if en is None:
        missing.append(v["ja"])
        continue
    too_long.update(ln for ln in en.split("\n") if len(ln) > WIDTH)
    out[addr] = {"ja": v["ja"].replace("{99,99,99}", " "), "en": en}
if too_long:
    raise SystemExit("lines over %d cells: %r" % (WIDTH, sorted(too_long)))
doc = {"_doc": "English for /DAT1/KOUBAI.BIN (the おまけ shop): item names, descriptions and the two "
               "shopkeepers. Format B3 (3-byte glyphs over the shop atlas, 0x80 line break, 0x81 end); lines "
               "<= 20 cells, <= 4 lines; Yes/No prompts keep the stock cursor columns. Generated by "
               "tools/localization/make_koubai_en.py (edit the templates there).",
       "by_address": out}
json.dump(doc, open(DST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "translated;", len(missing), "missing:", missing[:5])
