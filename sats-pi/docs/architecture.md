# Architecture
Navigateur / APK / Desktop  ->  HTTPS  ->  backend FastAPI  ->  Lightning (Blink) + PI-SPI (partenaire agréé)
Le front est unique (apps/web). Capacitor et Tauri ne contiennent aucune logique métier : ils chargent le build de apps/web.
Le backend est la seule source de vérité (taux, frais, statuts). Le front n'effectue aucun calcul de prix définitif.
