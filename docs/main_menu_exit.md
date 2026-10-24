# Exit dans MODE SELECT

L'entrée **Exit** se trouve après **Options**. Bas depuis Options, ou Haut
depuis Youth Diary 2, la sélectionne. Le bouton de validation du jeu, Cercle,
ferme le port par son chemin normal `SDL_QUIT`. Croix annule la sélection.
Haut retourne à Options et Bas revient à Youth Diary 2. Les commandes
clavier suivent les affectations de manette du port. Les deux manettes sont
acceptées.

L'extension appartient au kit : `runtime/menu_exit.cpp`, raccordée au démarrage
par `codegen_setup.c` et compilée par `CMakeLists.txt`. Elle n'édite ni le disque,
ni le code généré, ni les sous-modules. Elle reste disponible avec le disque
japonais ; les textes supplémentaires du port sont en anglais.

## Détection et rendu

Les trois pointeurs d'entrée de `/DAT1/MODESEL.BIN`, aux offsets 0, 4 et 8,
valent `0x800A3F84`, `0x800A4974` et `0x800A5730`. L'extension exige ces trois
valeurs en RAM et l'état actif de la structure de menu `0x801C8000`.
Le mode courant est publié à `0x801F6330` par le code à `0x800A41D0`.
Les identifiants internes sont 6 pour Youth Diary 2 et 3 pour Options.

Le curseur original reste sur l'une de ces deux entrées lorsque Exit est
sélectionné. Les entrées destinées à Exit sont consommées jusqu'au relâchement,
y compris les mots d'appui déjà reçus par le jeu à `0x801F5E00`, `0x801F5E02`,
`0x801F5E80` et `0x801F5E82`, lus par MODESEL à partir de `0x800A3FBC`.
Les autres mouvements restent gérés par le jeu.

Le cadre et les libellés masqués par le sélecteur d'origine sont relus dans
l'atlas déjà chargé en VRAM, sans embarquer de ressource du jeu dans le kit.
La nouvelle ligne occupe l'espace sous Options. Les transferts GP0 A0 écrivent
les deux trames entrelacées, pour éviter de laisser une ligne sur deux de
l'ancien texte en 480i. L'état de masquage GPU est restauré après le dessin.
Le rendu est limité à l'écran MODE SELECT 512 × 480.

## Vérification

```powershell
cmake -S . -B build-diagnostic -DNSN2_BUILD_TESTS=ON
cmake --build build-diagnostic --target psx-runtime menu-exit-test
ctest --test-dir build-diagnostic --output-on-failure
```

Le test de comportement couvre la navigation circulaire, la validation,
l'annulation, les boutons maintenus et le changement de scène. Le contrôle
dans le jeu utilise le pilote SDL `dummy`, le rendu logiciel et le port de
debug 4370, sans fenêtre sur l'écran du propriétaire. La séquence complète
teste les deux accès à Exit, l'annulation, le retour à Arcade/Options/Youth
Diary et la fermeture effective avec code de sortie 0.

Les captures de l'extension passent par `present_shot` et sa confirmation
`present_shot_seq` : une capture VRAM demandée au début du VBlank précède le
dessin de l'interface hôte. Les preuves locales restent dans
`localization/work/exit_validation/`, ignoré par Git.

`NSN2_EXIT_TRACE=1` active le suivi des appuis et de la sélection sur stderr.
Le test e2e final, notamment la présentation OpenGL et la manette physique,
reste effectué par le propriétaire sur la version habituelle du port.
