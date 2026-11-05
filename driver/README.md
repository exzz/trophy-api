# Pilote ODBC HFSQL Linux (à déposer ici)

Ce dossier doit contenir le **pilote ODBC HFSQL v25 pour Linux 64 bits** et
ses dépendances PC SOFT. Il n'est PAS sur serveur1 (machine Windows : elle n'a
que les DLL natives `wd250hf.dll`, pas le `.so` Linux).

Fichier principal attendu : `WD250hfo64.so`
(+ les bibliothèques `.so` livrées dans le même pack, dont le pilote dépend).

## D'où le prendre

1. **Votre installation WINDEV 25** (recommandé, lié à votre licence) :
   dossier `INSTALL\ODBC\`, fichier `wxpackodbclinux64.zip`
   (ou `ODBC25LINUX64PACK...zip`). Décompresser son contenu ici.
2. **Centre de téléchargement PC SOFT** (éditeur), pack ODBC Linux 64 bits de
   la version 25.

Après dépôt :

```bash
cd /home/exz/local/trophy
chmod +x driver/*.so
source env.sh
ldd driver/WD250hfo64.so | grep "not found"   # doit ne rien renvoyer
```

Si `ldd` signale des dépendances manquantes, c'est qu'il manque des `.so` du
pack : les ajouter ici (ils se chargent via `LD_LIBRARY_PATH`, réglé par
`env.sh`).

## Rappel important

Le pilote Linux de HFSQL fonctionne avec **iODBC** (pas unixODBC). C'est déjà
le cas ici : `pyodbc` a été compilé contre `libiodbc.so.2`.
