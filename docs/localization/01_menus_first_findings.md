# 01 — Menus : premiers constats (24 octobre 2026)

Preuves locales (ignorées par git) : `localization/work/`.

## Résumé

1. **La capture automatique de `text_xlate` ne voit pas les textes du jeu.**
   Les menus et dialogues ne transitent pas par des chaînes Shift-JIS passées
   en argument aux appels. Le moteur `[[entry]]` (substitution de chaînes) ne
   s'applique donc pas tel quel.
2. **Les menus sont des images.** Les libellés (options, modes, clubs, stats)
   sont des textures 4 bpp pré-dessinées en VRAM, pas du texte composé
   caractère par caractère. Leur traduction relève du **niveau texture**
   (`[[vram_patch]]` ou remplacement de fichier disque).
3. **Le dialogue utilise une police**, composée à l'exécution (encodage encore
   inconnu). Il faudra une analyse Ghidra du moteur de texte avant toute
   traduction des dialogues.

## Méthode

- Build : `build-diagnostic/` (`-DPSX_DEBUG_TOOLS=ON`), lancé en
  `--headless --no-launcher` avec `--disc` / `--bios` absolus.
- Env : `PSX_XLATE_CAPTURE=1` (la capture est **désactivée par défaut** dans
  `psxrecomp @ 5420458`, voir `runtime/src/text_xlate.cpp` l.420-425 et
  l.921-923) et `PSX_LANG=jp` (aucune substitution).
- Pilotage : port debug `127.0.0.1:4370`, commandes `press`, `screenshot`,
  `xlate`, `read_ram`, `vram_peek`.
- **Piège manette :** `press` / `set_input` prennent le **mot brut actif-bas**
  (repos = `0xFFFF`). START = `0xFFFF ^ 0x0008` = `0xFFF7`. Envoyer `8` revient
  à appuyer sur tous les boutons sauf START.
- **Piège VRAM :** `vram_peek` limite chaque requête à 128×32 mots ; lire la
  VRAM complète en tuiles.

Parcours : intro → écran titre (« PRESS START BUTTON ») → `MODE SELECT` →
mode histoire (熱血青春日記) → 入学する → premier dialogue (4月1日).
Captures : `localization/work/captures/` (`a_sheet.png`, `c_sheet.png`,
`d00.png`).

## Constat 1 — inventaire `text_xlate`

Après le parcours ci-dessus : 12 enregistrements, tous parasites (octets
binaires interprétés comme Shift-JIS), par ex. PC `800114b0` / RA `80011408`
sur des tampons `801e9xxx`, et PC `80015eac` sur une table de kana en
`800e8956` (30 octets, 3572 appels : probablement une table de conversion,
**piste à vérifier** pour l'encodage du dialogue).

Recherche Shift-JIS dans un dump RAM complet pris pendant le dialogue
(`localization/work/ram_dialog1.bin`, 2 Mio à partir de `0x80000000`) :

| Texte visible | Trouvé en Shift-JIS ? |
|---|---|
| ようこそ / よろしく (dialogue) | non |
| 入学する / つづきをはじめる (menu) | non |
| モードセレクト | non |
| 熱血青春日記 | oui, en `0x80084464` et `0x800cab08`, mais **uniquement** dans le titre de sauvegarde carte mémoire `私立ジャスティス学園熱血青春日記２のセーブデータです` (précédé de `BISLPS-02120`) |

Conclusion : ni le menu ni le dialogue ne stockent leur texte en Shift-JIS en RAM.

## Constat 2 — les menus sont des textures 4 bpp

Dump VRAM complet pendant le dialogue : `localization/work/vram/dialog1.bin`
(1024×512 mots 16 bits), vues `dialog1_15bpp.png` et `dialog1_4bpp.png`, et
pages de texture 4 bpp découpées `tp_<x>_<y>.png` (64 mots = 256 px de large,
256 lignes).

| Page VRAM (x, y en mots) | Contenu observé (lecture visuelle) |
|---|---|
| (512, 256) | chiffres, jours `月火水木金土日`, stats `攻撃力 防御力 体力 知力 根性 …`, clubs `野球部 相撲部 化学部 美術部 演劇部 帰宅部 吹奏楽部 サッカー部 バレー部`, `速い 遅い`, `試験の練習` |
| (576, 256) | options : `メッセージスピード 爆裂シュート 終了 一括 サービスエース ＰＫ戦 ホームラン競争 進める バックアップ 移動 普通 ミニゲームの練習 ステータス 日記`, `Doki-Waku-Dance` |
| (960, 0) | `オプション ゲーム キー操作変更 サウンドテスト おまけ 記録 ム`, `次ページへ 前ページへ おまけ画面に戻る START` |
| (640, 256) | noms d'écoles et de personnages (`パシフィック高校 太陽学園 外道高校 ジャスティス学園 五輪高校`, `ステータス アイテム 友好度`, fragments de noms) : **page composite**, peut-être un cache de glyphes |
| (704, 256) | icônes de visages (pas de texte) |
| 15 bpp (x ≥ 832) | grands libellés colorés, `GAME OVER`, `校門前` |

Ces libellés sont dessinés comme des images entières (et non glyphe par glyphe).
La traduction des menus passe donc par :

- `[[vram_patch]]` de `text_xlate` (bandes pré-rendues, voir
  `psxrecomp/docs/STRING_TRANSLATION.md`, annexe « VRAM-strip patch layer »),
  avec contrôle exact de la région source avant écriture ;
- ou un `[[overlay]]` disque (mod) sur le fichier qui contient ces textures,
  une fois ce fichier identifié.

L'écran `MODE SELECT` n'était plus en VRAM au moment du dump : refaire un dump
sur cet écran avant de le traiter.

## Constat 3 — le dialogue

Le texte du dialogue (`『熱血青春日記２』へようこそ！ これから一年間よろしくね。`)
est rendu avec une police (glyphes réguliers), mais son texte n'existe pas en
Shift-JIS en RAM. Hypothèses à vérifier (aucune n'est prouvée) :

- script encodé en index de glyphes (1 ou 2 octets) ;
- la table de 30 octets en `0x800e8956` lue par PC `0x80015eac` sert à cette
  conversion ;
- les glyphes sont copiés d'une police en RAM vers le framebuffer ou vers une
  page cache (voir la page (640, 256)).

**Prochaine étape côté analyse (Ghidra) :** identifier la fonction qui
dessine un caractère de dialogue (appelée à chaque glyphe pendant l'effet
machine à écrire), remonter au pointeur de script, et documenter l'encodage
dans `ghidra_findings.md`.

## Travail restant sur les menus

- Traduction des **menus** (textures) : inventaire écran par écran (dumps VRAM
  sur chaque menu), extraction des pages 4 bpp avec leur CLUT, redessin en
  anglais, réinjection via `[[vram_patch]]` ou overlay disque.
- Points de départ : pages (512, 256), (576, 256) et (960, 0) ci-dessus.
- Le code de langue reste à vérifier (`jp` désactive la substitution ; `ja`
  dans le plan).
