# 03 — Menus : périmètre, mécanismes, inventaire (24 octobre 2026)

Preuves locales : `localization/work/menu/`, captures dans `localization/work/captures/`.

## Périmètre et directive du propriétaire

- **Objectif : traduire tous les menus en anglais.** Le reste du texte en jeu
  n'est pas prioritaire ; les dialogues relèvent d'une phase ultérieure
  éventuelle (outils déjà prêts, voir `02_dialogue_engine.md`).
- **Règle absolue sur les textures :** une texture traduite garde **exactement
  les mêmes dimensions** (largeur, hauteur, profondeur de couleur, position
  VRAM, CLUT). Elle n'est **jamais agrandie, réduite ni étirée**, et le texte
  n'est jamais compressé horizontalement pour rentrer.
- **Si la traduction ne tient pas ou paraît trop serrée** (lettres collées,
  marges disparues, lisibilité dégradée) : **trouver une autre traduction**
  plus courte (synonyme, abréviation usuelle, reformulation), garder un rendu
  aéré cohérent avec le style d'origine, et consigner le choix dans le glossaire.

## Les trois mécanismes de texte de menu

| Type | Comment le texte est stocké | Comment traduire | Travail |
|---|---|---|---|
| **A. Libellés pré-dessinés** | images TIM 4 bpp dans un fichier `/DAT2/*.BIZ` compressé | redessiner l'image à dimensions identiques, réinjecter le TIM | texte anglais, redessin, réinjection |
| **B. Atlas d'écran + chaînes d'octets** | atlas de glyphes 20×20 propre à l'écran (TIM dans un `.BIZ`) ; chaînes dans le code de l'écran (`/DAT1/*.BIN`) : `[nombre][col,ligne]×nombre` | ajouter des glyphes latins dans l'atlas (mêmes dimensions) **et** réécrire les chaînes | texte, chaînes, glyphes latins |
| **C. Système de dialogue** | répliques u16 dans un bloc script (écran de sauvegarde, oui/non…) | `tools/localization/nsn2script.py` + `nsn2text.py` | texte |

### A. Libellés pré-dessinés — exemple `MODE SELECT`

Écran chargé avec `/DAT2/MENU.BIZ` (compressé, 383 296 octets → 653 312
décompressés) et le code `/DAT1/MODESEL.BIN` (chargé en `0x800A2000`).
`MENU.BIZ` décompressé contient **45 TIM standard** (`tools/localization/psxtim.py scan`) :

| TIM | Offset | VRAM (mots) | Taille (mots) | Contenu |
|---|---|---|---|---|
| #0 | `0x000000` | (768, 0) | 256×256, 4 bpp, 13 CLUT en (256,480) | atlas de glyphes + grands titres `オプション / ゲーム / キー操作変更 / サウンドテスト / おまけ / 記録`, bloc `次ページへ / 前ページへ / おまけ画面に戻る START` |
| #1 | `0x020800` | (896, 256) | 36×96 | à identifier |
| #2 | `0x022800` | (512, 256) | 320×256, 4 bpp, 32 CLUT en (0,482) | **tous les libellés de `MODE SELECT`** (deux tailles), en-tête `MODE SELECT`, `現在のポイント`, chiffres |
| #3–#16 | `0x04B800`… | (832, 256) | 44×112 chacun, **sans CLUT** (palette fournie en VRAM) | **les 14 textes de description** des modes (un par entrée) |
| #17–#30 | `0x06E800`… | (512, 0) | 25×114 | illustrations des modes (pas de texte) |
| #31–#44 | `0x083800`… | (640, 0) | 32×96 | vignettes (pas de texte) |

Entrées de `MODE SELECT` (dans l'ordre) : 熱血青春日記2, 一人で遊ぶ, 対戦,
リーグ戦, 団体戦, トーナメント戦, 協力戦, トレーニング, 試験に出る実技'99,
五輪祭, EDIT登録, おまけ, 記録, オプション. Encadré : `現在のポイント … PTS`.

Rendus de travail : `localization/work/menu/MENU_BIZ_XX.png`,
`sheet_832.png` (descriptions), `p2_sheet.png` (libellés).

### B. Atlas d'écran + chaînes — exemple `リーグ戦` (écran du nombre d'équipes)

Fichiers : code `/DAT1/PLSEL3.BIN` (en `0x800A2000`), atlas `/DAT2/SELP3.BIZ`
(page VRAM (768, 0), glyphes 20×20, 12 par ligne). L'atlas réel en VRAM
(`localization/work/` : `league_p768.png`) ne contient que les glyphes utiles à
l'écran ; latin limité à `P H S` et aux chiffres.

Le dessinateur (overlay, boucle autour de `0x800A4028`) lit pour chaque glyphe
**deux octets `col, ligne`** (`u = col×20`, `v = ligne×20`) via `s2`.
Exemple prouvé : `0x800A2490` = `08` puis
`06 05 · 07 05 · 08 05 · 09 05 · 07 01 · 08 01 · 09 01 · 0A 01`
= 8 glyphes `何 組 参 加 し ま す か` (« 何組参加しますか »).

Piste pour l'anglais sans changer les dimensions : dessiner dans les cellules
libres de l'atlas des **paires de lettres latines** (deux lettres de 10 px par
cellule de 20 px), puis réécrire la chaîne avec ces cellules. Le nombre de
cellules par chaîne et l'espace des chaînes dans l'overlay sont limités : à
mesurer écran par écran.

### C. Système de dialogue

Écrans observés : boot (`ファイルがありません / オートロードしませんでした`),
menu de sauvegarde du mode histoire (`どれをおこないますか? セーブ ロード
メニューに戻る`, `はい / いいえ`, groupe 5 de `MGK04.BIZ`). Traduisibles avec les
outils de `02_dialogue_engine.md` (≤ 19 caractères par ligne, ≤ 4 lignes).

## Réinjection d'une texture (procédure)

1. Décompresser le `.BIZ` : `nsn2lz.decompress(file_bytes)`.
2. Repérer le TIM : `psxtim.scan(raw)` (offset, bpp, position VRAM, CLUT).
3. Remplacer **uniquement** les octets de pixels du TIM (même taille, même bpp,
   indices de la même CLUT), sans toucher l'en-tête.
4. Recompresser **à la taille exacte du fichier d'origine** :
   `nsn2lz.compress_exact(raw, stock_size)` (obligatoire : un flux plus court
   bloque le chargement ; testé sur `MENU.BIZ` en 3 s, aller-retour identique).
5. Écrire le flux aux mêmes secteurs (LBA d'origine) : pendant le développement
   sur une **copie** du disque (`localization/work/testdisc/`) ; en livraison,
   via un `[[overlay]]` disque d'un paquet de mod.

## Formats de chaînes rencontrés

| Format | Où | Encodage d'un glyphe | Fin |
|---|---|---|---|
| B1 | `NEWOPT.BIN`, EXE, `MGTIT.BIZ`, `KANRI.BIN` | u16 `bloc*0x100 + ligne*0x10 + col` (atlas commun ; kanji propres à l'écran au-delà de la ligne 9 du bloc 1) ; `0xFFF` = espace ; `0xFFxx` = glyphe d'un atlas d'écran (`EDITMOJI`) | compteur u16 en tête |
| B2 | `PLSEL3.BIN` (League) | 2 octets `(col, ligne)` dans l'atlas de l'écran | compteur u8 en tête |
| B3 | `KOUBAI.BIN` (boutique) | 3 octets `(bloc, col, ligne)` | `0x80` saut de ligne, `0x81` fin |

Outils : `nsn2menu.py` (B1 : décodage, reconstruction de pool avec relocalisation
des pointeurs, chaînes non traduites figées à leur adresse, garde-fou contre
l'effacement de données hors chaînes), `patch_newopt.py`, `patch_exe_strings.py`,
`patch_mgtit.py`, `patch_overlay.py` (générique, configuration par fichier).
Place disponible : pool d'origine + fin inutilisée du dernier secteur (les
overlays `.BIN` sont chargés par secteurs entiers) ; pas de place libre dans l'EXE.

## Inventaire (état au 24 octobre 2026)

| Écran | Fichiers | Type | Statut |
|---|---|---|---|
| Titre | `TITLE.BIZ` | A | déjà en anglais |
| Démarrage / carte mémoire | EXE | B1 | **traduit** (pool EXE) |
| `MODE SELECT` | `MENU.BIZ` TIM #2, #3-#16 | A | textes anglais rédigés (`menus.json`), image à faire |
| Options, Game System, test son | `NEWOPT.BIN` | B1 | **traduit** (titres 40×40 restés en japonais) |
| Records | EXE | B1 | **traduit** |
| Aide des réglages système | `OPTINFO.TIZ` (5 TIM) | A | à faire (image) |
| Titre du mode histoire | `MGTIT.BIZ` | B1 | **traduit** |
| EDIT登録 | `KANRI.BIN` (+ `EDITMOJI.TIZ`) | B1 | **traduit** (boutons `0xFFxx` en japonais) |
| Mot de passe EDIT | `PASS.BIN` | ? | à analyser |
| おまけ (menu) | `KOUBAI0.TIZ` | A | à faire (image) |
| Boutique | `KOUBAI.BIN` | B3 | format prouvé, ~100 chaînes à traduire |
| Sélection des personnages (1P, Training) | `SELP1.BIZ`, `PLSEL1.BIN` | A (+ noms) | à faire |
| League / Tournament | `PLSEL3/4.BIN`, `SELP3/4.BIZ` | B2 + A | atlas d'écran sans latin : image + chaînes |
| 五輪祭 | `MINITTL0/1.BIZ`, `MINISEL.BIN` | A | à faire (image) |
| Versus / Team / Co-op | (2ᵉ manette requise) | ? | à vérifier |
| Titres 40×40 (Options, Sound Test…) | atlas `MENU.BIZ` bloc 3 | A | grandes lettres latines à dessiner |

Méthode pour un nouvel écran : capture + dump VRAM + `dma_cdrom_history`
(fichiers chargés) + anneau GP0 (`gpu_frame_dump`) pour voir quelle page VRAM
dessine le texte ; `wtrace_range` sur un paquet de sprite pour remonter au code
et à la chaîne (`localization/work/tools/glyphtrace.py`).
