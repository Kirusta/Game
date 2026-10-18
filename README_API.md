# Cyber Tower Defense datubāze

Datubāze glabā spēlētājus un viņu labākos Infinite Mode viļņus failā `game.db`.

## Palaišana

Atver termināli spēles mapē un izpildi:

```powershell
pip install -r requirements.txt
uvicorn api.main:app --reload
```

Pēc tam atver `http://127.0.0.1:8000/docs`.

## Pārbaudes secība

1. Pirmajā spēles ekrānā ievadi lietotājvārdu un nospied `ENTER`.
2. Ievadot to pašu lietotājvārdu vēlreiz, spēle atjauno saglabātās kartes un Skill Tree progresu.
3. Pēc Infinite Mode zaudējuma spēle automātiski nosūta sasniegto vilni uz datubāzi.
4. `http://localhost:8000/rules` rāda noteikumus.
5. `http://localhost:8000/leaderboard` parāda TOP 10 Infinite Mode rezultātus.
6. `http://localhost:8000/database` parāda visus spēlētājus, rezultātu vēsturi un saglabāto progresu. Paroļu jaucējvērtības un pieslēgšanās tokeni drošības dēļ netiek rādīti.

Serveris izmanto SQLite, tāpēc rekordi paliek arī pēc servera restarta.
