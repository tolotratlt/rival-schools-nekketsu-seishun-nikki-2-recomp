# 02 — Moteur de dialogue : encodage, police, script (24 octobre 2026)

Ghidra n'était pas lancé : analyse faite avec le runtime de diagnostic
(`build-diagnostic`, port 4370), le désassemblage capstone de `disc/SLPS_021.20`
et une lecture ISO9660 du `.bin`. Outils réutilisables :
`localization/work/tools/` (ignoré par git). Preuves : `localization/work/`.

## Résumé

| Élément | Résultat | Confiance |
|---|---|---|
| Encodage du texte | **u16 little-endian = numéro de glyphe** (pas de Shift-JIS) | prouvé |
| Police fixe | RAM `0x800D0180`, 20×20 px, 4 bpp, **200 octets/glyphe**, codes `0x0000`–`0x0120` | prouvé |
| **Latin présent** | `A–Z` `0x0B–0x24`, `a–z` `0x25–0x3E`, `1–9,0` `0x01–0x0A`, ponctuation `0x3F–0x56` | prouvé (rendu) |
| Kanji | codes `≥ 0x0129`, **propres à chaque scène** (chargés avec le script) | prouvé sur 1 scène |
| Table complète | `localization/nsn2_charmap.json` | prouvé sauf `0x0000`/`0x00D0` |
| Script en RAM (scène d'ouverture) | bloc en `0x80101000` : table de pointeurs u32 puis texte | prouvé sur 1 scène |
| Codes de contrôle | `0x0000` espace, `0x3000` saut de ligne, `0x3001` fin de bulle (prouvés, §6.4) ; `0x3003 <arg>` couleur | prouvé / hypothèse |
| Fichiers disque | `/DAT2/*.BIZ`, `*.BZZ`, **LZ 16 bits** (`FUN_80015EAC`), codec `tools/localization/nsn2lz.py` | prouvé (§6.2) |
| Preuve de concept | réplique d'ouverture affichée en anglais depuis une copie du disque | prouvé (§6.4) |
| Affichage | glyphes chargés un par un en VRAM (`LoadImage` 5×20 mots) dans la page (768,256), puis dessinés en sprites | prouvé |

## 1. Rendu à l'écran

Pendant l'avance d'un dialogue (bouton **CIRCLE**, `press buttons=0xDFFF`),
l'anneau GP0 (`gpu_frame_dump`) montre, à la trame 47818, 25 chargements
CPU→VRAM `0xA0` de **5×20 mots (20×20 px en 4 bpp)** aux positions
`(768+5k, 256)`, `(768+5k, 276)`, `(768+5k, 296)`… : **12 glyphes par rangée,
rangées de 20 lignes**. La page (768,256) est ensuite échantillonnée par des
sprites `0x64` (≈17 par trame, `ra 0x800648C8`).

`LoadImage` (libgpu) = `0x80062630` (appelle `table->dws` à
`*(0x80092038)+0x20` = `0x80063B4C`). Ses 9 appelants directs dans l'EXE ne
sont pas la boucle de glyphes (TIM/streaming) : **la boucle d'upload de
dialogue n'est pas encore localisée** (appel probable par pointeur, ou via une
autre primitive). Ce n'est pas bloquant pour la traduction.

Capture : `localization/work/captures/adv2.png`, anneau GP0 :
`localization/work/adv2.json`.

## 2. Police

Recherche dans la RAM (`ram_line2.bin`) des 200 octets du 1er glyphe de la
ligne (lu en VRAM) : trouvé en `0x800DB3A0` (と), puis `0x800DC340` (り),
`0x800DA4C8` (あ), `0x800DA720` (え). Écarts multiples de 200 octets, ordre du
syllabaire : あ = index 209 → base `0x800DA4C8 − 209×200 = 0x800D0180`.
Rendu complet des codes 0–0x14F : `localization/work/font_codes.png`.

Disposition (détail dans `nsn2_charmap.json`) :

| Codes | Contenu |
|---|---|
| `0x0000` | vide (rôle à confirmer : espace ou terminateur) |
| `0x0001–0x000A` | `1`…`9`, `0` |
| `0x000B–0x0024` | `A`…`Z` |
| `0x0025–0x003E` | `a`…`z` |
| `0x003F–0x0056` | `@ # % ? & ♥ + * > < $ ! — ^ . ★ ☆ ← → 。 、 ー ＝ ：` |
| `0x0057–0x00A7` | katakana (ア…ッ) |
| `0x00A8–0x00CF` | symboles (`ー ＿ ， ・ ； 〃 々 － ／ ＼ ～ … ‘ ’ “ ” （ ） 「 」 『 』 …`) |
| `0x00D0` | glyphe « espace visible » (rôle à confirmer) |
| `0x00D1–0x00FE` | hiragana あ…ん |
| `0x00FF–0x0120` | hiragana voisés/petits (が…ょ) |
| `0x0121–0x0128` | icônes boutons ○ □ × △ L1 L2 R1 R2 |
| `≥ 0x0129` | kanji de la scène (variables) |

**Conséquence majeure :** l'anglais s'écrit avec les glyphes existants, sans
toucher à la police. Limite : cellules **fixes de 20 px** (pas de chasse
proportionnelle). Le moteur range 12 glyphes par rangée de page VRAM ; la
largeur réelle d'une ligne affichée et le nombre de lignes par bulle restent à
mesurer (la ligne d'exemple affiche ≈ 14–16 caractères).

## 3. Script

Recherche de « とりあえ » encodé `E4 F8 D1 D4` (u16 LE) : trouvé en
`0x80101064` (et une copie en `0x80102488`). Décodage du bloc (`0x80101000`) :

```
+0x00  table de pointeurs u32 (0x8010235C, 0x80103780, 0x80105938, ...), fin = 0x00000000
+0x40  {3003}{0000} 『 熱 血 青 春 日 記 ２ 』 {3003}{00FF} へようこそ！{3000}
       これから一年間よろしくね。{3001}
       とりあえず、入学試験が始まるまで、{3000}私が案内するわね。{3001} ...
```

(`熱血青春日記一年間入学試験始私案内…` = codes `0x0129`–`0x013F` de la scène.)

Codes de contrôle observés (hypothèses à confirmer en modifiant un octet) :

- `0x3000` : saut de ligne dans la bulle ;
- `0x3001` : fin de bulle, attente du bouton ;
- `0x3003 <u16>` : changement de couleur (`0x0000` avant le titre jaune,
  `0x00FF` après) ;
- non encore vus : choix multiples, nom du locuteur, insertion de variables.

## 4. Sur le disque

Le même texte apparaît dans plusieurs fichiers de `/DAT2/`
(`MGC01.BIZ`, `MGC03.BIZ`, `MGG04.BZZ`, `MGG04O.BIZ`, `MGK09.BIZ`, …) :
probablement un fichier par route/personnage. Les octets y sont **entrecoupés
de mots `0x0000` réguliers** (ex. `MGG04.BZZ` offset `0x5E4EC`), signature
probable d'une compression LZ à drapeaux 16 bits. Le bloc RAM de la scène
d'ouverture n'a été retrouvé tel quel dans **aucun** fichier `/DAT2/` : il est
décompressé au chargement. Liste des fichiers : `tools/iso.py list` (947
fichiers).

## 5. Pistes de mise en œuvre

Le mécanisme existant `msg_inplace` de `text_xlate` (`[[entry]]` + `ram_addr`)
**ne convient pas tel quel** :

- il encode en Shift-JIS pleine chasse (`fw_sjis_for_ascii`) et avec les codes
  de contrôle d'un autre jeu (`0xFFFE`, `0xFC30`, `0xFC10`) ;
- il **tronque** à la longueur japonaise, alors que l'anglais est en général
  plus long en nombre de cellules.

Options, de la moins à la plus intrusive :

1. **Profil d'encodage NSN2** dans `text_xlate` (le framework prévoit
   `EncodingProfile`) : UTF-8 → codes `nsn2_charmap`, contrôles `0x3000/3001/3003`.
   Extension isolée et réutilisable.
2. **Réécriture du bloc script en RAM** après décompression : détecter un bloc
   connu (empreinte du texte japonais), puis écrire la version anglaise **et
   recalculer la table de pointeurs** pour absorber les longueurs différentes
   (vérifier la place disponible dans le tampon).
3. **Réécriture des fichiers `/DAT2/`** (décompresser, éditer, recompresser,
   `[[overlay]]` disque) : nécessite le format LZ exact et que les fichiers ne
   grossissent pas au-delà de leurs secteurs.

L'option 2 (éventuellement avec le profil de l'option 1) évite la
recompression et reste compatible avec le retour au japonais.

## 6. Mise à jour — décompression et preuve de concept (même jour)

### 6.1 Qui écrit le script

`wtrace_range lo=0x80101000 hi=0x80101080` armé avant le mode histoire, puis
`wtrace_dump` (`localization/work/wtrace_script.json`) : deux écrivains seulement,

- le **DMA canal 3** (CD-ROM), données brutes ;
- l'instruction **`0x80015F14`** dans **`FUN_80015EAC`**, appelée par le pilote
  en flux **`FUN_80015D04`** (`ra 0x80015E34`).

`dma_cdrom_history` sur la même fenêtre (`cd_2900.json`) : le fichier lu dans
l'anneau `0x801F9000` est **`/DAT2/MGK04.BIZ`** (LBA 109905, 207 226 octets).

### 6.2 Format de compression (prouvé)

`FUN_80015EAC(a0 = source, a1 = fin du secteur, a2 = destination)`, mots u16 LE :

- un mot de drapeaux, puis 16 éléments, bit de poids fort d'abord ;
- bit 0 : littéral, le mot suivant est copié ;
- bit 1 : `W` = mot suivant ; longueur `W >> 11`, distance `W & 0x7FF` mots ;
  si longueur 0, la longueur est le mot suivant ; longueur 0 et distance 0 = fin.

Pilote `FUN_80015D04` : anneau de 0x4000 octets en `0x801F9000`, traitement
secteur par secteur (0x800), état en `0x80099C90` (écriture anneau),
`0x80099C94` (source), `0x80099C98` (destination), `0x80099C9C`/`0x80099CA0`
(compteurs). À chaque retour au début de l'anneau, les 0x40 premiers octets sont
recopiés en `0x801FD000` : **un groupe ne doit pas dépasser 0x40 octets**
(l'original en fait au plus 40).

Codec Python : `tools/localization/nsn2lz.py` (`decompress`, `compress`,
`compress_exact`). `MGK04.BIZ` → **333 824 octets** décompressés, consommant
exactement le fichier ; ce contenu est chargé **tel quel en `0x800D0000`** :
la police est à l'offset `0x180`, la première réplique à l'offset `0x31020`.
Aller-retour décompression/recompression identique.

### 6.3 Contrainte de taille

Un flux plus court que l'original (marqueur de fin anticipé, reste à zéro) fait
**bloquer le jeu sur « NOW LOADING »** (le pointeur de destination part en
`0x80156E04`). `compress_exact()` produit un flux de **la taille exacte du
fichier d'origine**, marqueur de fin dans les derniers octets, références
limitées à 31 mots (groupes ≤ 34 octets) : c'est cette version qui fonctionne.
Marge disponible pour `MGK04.BIZ` : le flux compact fait ~127 Ko pour 207 Ko
autorisés, soit **~80 Ko de place** pour du texte plus long.

### 6.4 Preuve de concept

Script `localization/work/tools/poc_patch.py` sur une **copie** du disque
(`localization/work/testdisc/test.bin`, original intact) : remplacement à
longueur égale (34 mots) de la première réplique par

```
{3003}{0000} Welcome to {3003}{00FF}{3000} Nekketsu Nikki 2!! {3001}
```

Résultat en jeu (`captures/poc_english_line.png`) : **« Welcome to /
Nekketsu Nikki 2!! »** s'affiche dans la bulle ; les répliques suivantes restent
correctes (`captures/poc_next_lines.png`). Confirmé au passage :

- `0x0000` = **espace** ;
- `0x3000` = **saut de ligne**, `0x3001` = fin de bulle ;
- environ **19–20 caractères latins par ligne** (cellules de 20 px).

## 7. Structure du bloc script et répliques de longueur libre (prouvé)

Bloc script de `MGK04.BIZ` décompressé (offset `0x31000`, RAM `0x80101000`) :

```
0x31000  table maîtresse : 7 × u32 (adresse de chaque table de groupe), puis 0x00000000
0x31020  groupe 0 : répliques (u16), chacune alignée sur 4 octets
0x3235C  table du groupe 0 : 57 × u32 (adresse de chaque réplique), puis 0xFFFFFFFF
0x32444  groupe 1 : répliques …   table @0x33780 (57)  puis 0xFFFFFFFF
         groupes 2–6 : tables @0x35938 (170), @0x36474 (38), @0x36DE8 (38),
                       @0x373F0 (31), @0x37C20 (100), chacune fermée par 0xFFFFFFFF
0x37DB4  zéros jusqu'à 0x4A000 (bloc suivant) : emplacement de ~100 Ko, 28 Ko utilisés
```

- 491 répliques, **toutes alignées sur 4 octets** ; une réplique se termine par
  `0x3001`, suivi d'un mot `0x0000` de remplissage si besoin.
- Aucun mot de l'EXE ne pointe dans cette zone ; seules les tables du bloc la
  référencent (adresses absolues, chargement en `0x800D0000`).
- Les groupes 0 et 1 contiennent le même texte (variantes d'un même événement).
- Les écrans de choix sont aussi des répliques (ex. groupe 0 n°4 :
  `ゲームの説明…{3000}キャラの…`), avec un code `0x061E` répété qui sert
  probablement d'espacement : à étudier avant de les traduire.

Outils : `tools/localization/nsn2script.py` (`parse`, `build`, `replace`) —
reconstruction **identique à l'octet** du bloc d'origine ; `nsn2text.py`
(`encode` anglais → codes, `decode` codes → texte).

**Preuve de concept 2** (`localization/work/tools/poc2_longer.py`, copie du
disque) : répliques 0–2 des groupes 0 et 1 remplacées par un anglais **plus
long** que le japonais (bloc +336 octets, pointeurs recalculés, fichier
recompressé à taille exacte). Résultat en jeu :

- `captures/poc2_msg0_4lines.png` : **4 lignes de 19 caractères** tiennent dans
  la bulle (« Welcome to Nekketsu / Seishun Nikki 2! / Let's have a great /
  year together. ») ; la 4ᵉ ligne touche le bas du cadre ;
- `captures/poc2_msg2.png`, `poc2_next.png` : répliques 1 et 2 correctes, la
  réplique japonaise suivante et l'écran de choix s'affichent normalement.

Règle de mise en page établie : **≤ 19 caractères par ligne, ≤ 4 lignes par
réplique**.

## 8. Prochaines questions (ordre conseillé)

1. Les autres scènes : quels fichiers `/DAT2/` (le même texte existe dans
   `MGC01`, `MGC03`, `MGG04`, `MGG04O`, `MGK09`…) et le décalage du script dans
   chacun. La disposition `0x800D0000` / police à `0x180` est-elle commune ?
2. Extraction lisible pour les traducteurs : les kanji `≥ 0x0129` sont propres à
   chaque fichier (glyphes dans le TIM en tête de fichier) ; il faut les
   identifier (rapprochement des glyphes entre fichiers + table manuelle).
3. Couleur `0x3003 <arg>` (le titre n'est pas resté jaune avec `0x0000`) et
   code `0x061E` des écrans de choix.
4. Nombre de lignes par bulle, noms de locuteurs, choix.
5. Livraison : un `[[overlay]]` disque par fichier `/DAT2/` modifié (même taille,
   même LBA) dans un paquet de mod `mods/preloaded/packages/`. Le contenu traduit
   est dérivé des fichiers du jeu : décider avec le propriétaire ce qui peut être
   publié (générer les fichiers chez l'utilisateur à partir de son disque plutôt
   que les distribuer).
