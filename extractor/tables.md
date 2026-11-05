# Carte des tables HFSQL — base `Datas` (CS Trophy Gestion)

Relevé le 2026-11-01 par listing des fichiers `.fic` sur SERVEUR1 (lecture
seule, sans ouverture du contenu). Les noms de colonnes restent à obtenir.

## Tables utiles au projet

| Table            | Rôle probable                                  |
|------------------|------------------------------------------------|
| `Patients`       | Fiche patient (identité) — **cible**           |
| `Pat_ADR`        | Adresses patients                              |
| `Pat_MT`         | Médecin traitant                               |
| `Patient_INSi`   | Identité INS (INSi)                            |
| `Pat_AMO`/`Pat_AMC`/`Pat_Couv` | Couverture sociale / complémentaire |
| `Agenda`         | Rendez-vous (planning) — **cible**             |
| `Agenda_Archive` | Rendez-vous archivés                           |
| `TypeRDV`        | Types de rendez-vous                           |
| `PlageRéservée`  | Plages réservées                               |
| `AgendaOnLine`   | RDV pris en ligne                              |
| `Praticiens`     | Praticiens — **cible**                         |
| `Prat_SV`        | Praticien Sesam-Vitale                         |
| `Prat_Remplaçant`| Remplaçants                                    |
| `Poste`          | Postes/connexions                              |

## Autres tables présentes (contexte)

Soins, SOINS_CCAM, Soins_Traca, Devis, Dev_Ligne, Dev_Ligne_Alternative,
Devis_Materiaux, Devis_Modele(_Ligne), Plan_Actes, Plan_Tt, Traitement,
Actes(_Ref), ActeCoul, ActesCategorie(_Ref), ActesBridge, Hono_Libre, Remises,
Acompte, Recette, Reglement, EncourTP(_ligne), TiersPayant, Regle_TP,
Feuil_SS, FSE_Histo, FSE_ReponseADR, NOEMIE_* (A, R, AP, Vir, Regul, X),
STSConv/Corresp/Regroup, Courrier, Notes, Commentaire Dents, SchemaP,
Maj_Schema, Ordo_* (Pat, Lg, Lg_Motif, Consignes), Ordonnance, Prescription,
Medicament, MEDIC_Posology, Allergie, Etat_Medical, Med_Path/Cont,
Patient_ALDi, Pat_AT, Pat_Scr, Pat_ContextePatient, Email_* (Histo, PJ,
Modele), SMS(_Param, _Modeles), Mailing_Histo, CodePost/CodeVilles/CodePays,
Repertoire, Laboratoire/Labo_Disp, Materiaux, DM_*, Paramètres, SMS_Param, etc.
```
