# Hedge Fund Tool — Documentation Projet

## Objectif
Construire un outil personnel d'analyse actions et marché, pensé pour un usage quotidien de type analyste Long/Short Equity.

L'application doit être :
- rapide
- lisible
- stable
- utile pour prendre une décision
- simple à lancer localement

---

## État Actuel Du Projet

### Stack
- Python 3.9
- Streamlit
- yfinance
- pandas
- plotly
- requests

### Point d'entrée
- `app.py`

### Navigation
L'application utilise maintenant une vraie navigation multi-pages Streamlit avec barre latérale à gauche.

Pages actuellement disponibles :
- `Home`
- `Stock Analysis`
- `Market Overview`
- `Screener`
- `Relative Performance`
- `Watchlist`

### Lancement
L'outil se lance localement via :

```bash
cd ~/hedge-fund-tool
python3 -m streamlit run app.py
```

Un lanceur local existe aussi :
- `launch_hedge_fund_tool.command`
- raccourci bureau : `Ouvrir Outil HF.command`

Important :
- le lanceur ne tourne plus en fond
- il ouvre un Terminal visible
- le serveur Streamlit s'arrête quand la fenêtre Terminal est fermée

---

## Structure Du Code

### `app.py`
Rôle :
- configure l'application Streamlit
- déclare les pages
- lance la navigation

Ce fichier est maintenant volontairement léger.

### `ui.py`
Rôle :
- thème global
- styles CSS
- composants visuels réutilisables
- helpers de navigation entre pages

Contient notamment :
- la palette de couleurs
- le style sidebar
- `page_hero()`
- `card()`
- `table()`
- `open_page()`
- `open_stock_page()`

### `data.py`
Rôle :
- centraliser tout le fetching de données
- normaliser les données externes
- mettre en cache les appels

Contient notamment :
- recherche de tickers
- données actions
- historique de prix
- earnings
- recommandations analystes
- insiders
- marché global
- courbe des taux
- breadth
- fear & greed
- watchlist locale

### `charts.py`
Rôle :
- construire les graphiques Plotly
- ne pas mélanger fetching et rendu

Contient notamment :
- chandeliers
- technique multi-panneaux
- scorecard
- profitabilité
- earnings
- analystes
- secteurs
- courbe des taux
- performance relative
- screener scatter

### `utils.py`
Rôle :
- formatage
- fonctions de scoring
- helpers de lisibilité

### `pages/`
Chaque page est maintenant isolée dans son propre fichier.

- `pages/home.py`
  page d'accueil simple avec boutons de navigation

- `pages/stock_analysis.py`
  vue détaillée d'une société

- `pages/market_overview.py`
  cockpit marché

- `pages/screener.py`
  filtrage de tickers

- `pages/relative_performance.py`
  comparaison de deux actifs

- `pages/watchlist.py`
  suivi local de tickers

---

## Ce Que L'Outil Fait Aujourd'hui

### 1. Home
Page volontairement simple :
- ticker rapide
- bouton d'ouverture de `Stock Analysis`
- boutons directs vers les autres outils

### 2. Stock Analysis
Fonctionnalités actuelles :
- recherche de ticker par nom ou symbole
- sélection intelligente du ticker
- prix actuel et variation
- scorecard synthétique
- ratings type Zacks
- valorisation
- taille et structure
- profitabilité
- croissance
- santé financière
- positionnement
- earnings et estimations
- consensus analystes
- prix cibles
- transactions insiders
- analyse technique
- chandelier + MA20/50/200 + Bollinger + RSI + MACD

Points déjà sécurisés :
- gestion des `None` / `NaN`
- gestion plus robuste du calendrier earnings
- meilleure sélection du ticker exact
- protection contre les données Yahoo incomplètes

### 3. Market Overview
La page marché a été fortement enrichie.

Organisation actuelle :

#### Indicateurs critiques
- Fear & Greed
- VIX
- momentum 1 mois du S&P 500
- % du breadth au-dessus de la MA200
- leadership QQQ vs SPY
- pente de courbe 10Y - 3M

#### Indices directeurs
- S&P 500
- Nasdaq 100
- Dow Jones
- Russell 2000

Pour chacun :
- niveau
- performance 1 jour
- performance 1 mois
- performance 3 mois
- tendance
- Bull Bear Power (BBP)

#### Volatilité & sentiment
- Fear & Greed
- VIX
- VIX 3M
- ratio VIX / VIX3M

#### Breadth & leadership
- % > MA50
- % > MA200
- advance / decline
- leadership growth vs broad market
- proxy small caps vs large caps

#### Taux & intermarket
- 3M
- 5Y
- 10Y
- 30Y
- spreads de courbe
- or
- dollar

#### Rotation sectorielle
- performance journalière des secteurs via ETFs XL*

#### Courbe des taux
- graphique de courbe US

### 4. Screener
Fonctionnalités actuelles :
- liste custom de tickers
- filtres simples
- tableau de résultats
- scatter de screening
- ouverture rapide d'un ticker dans `Stock Analysis`

### 5. Relative Performance
Fonctionnalités actuelles :
- comparaison de deux actions
- performance base 100
- ratio historique
- z-score du ratio
- signal simple de spread

Robustesse :
- protection si les historiques ne se recoupent pas assez

### 6. Watchlist
Fonctionnalités actuelles :
- ajout / suppression de tickers
- persistance locale JSON
- ouverture rapide vers `Stock Analysis`

---

## Ce Qui A Été Corrigé Récemment

### Architecture / UX
- passage d'une app monolithique à une vraie app multi-pages
- sidebar latérale visible
- page d'accueil simplifiée
- thème sombre cohérent
- rendu plus stable entre mode clair et mode sombre macOS

### Robustesse données
- normalisation des taux US Yahoo (`^TNX`, `^TYX`, etc.)
- normalisation des formats `calendar`
- protections supplémentaires sur earnings / analystes / historique

### Graphiques
- correction de bugs Plotly
- correction de conflits de layout
- meilleure gestion des valeurs négatives
- stabilisation des graphes relatifs et screener

### Lancement local
- suppression du lancement en fond via `nohup`
- passage à un lancement ponctuel dans Terminal

---

## Limites Connues

### Source de données
Le projet dépend majoritairement de Yahoo Finance via `yfinance`.

Conséquences :
- certains champs changent de structure
- certaines données peuvent manquer
- certaines métriques sont approximatives ou indisponibles selon le ticker
- la fiabilité n'est pas celle d'un fournisseur institutionnel

### Market breadth
Le breadth actuel est un proxy basé sur grands ETFs indices/secteurs, pas encore sur tous les composants réels du S&P 500 ou du Nasdaq 100.

### Fear & Greed
Le projet tente de récupérer l'indice externe, sinon il utilise un proxy interne. C'est utile, mais ce n'est pas une mesure institutionnelle garantie.

### BBP
Le Bull Bear Power actuel est calculé de manière cohérente pour lecture rapide, mais il peut encore être enrichi par davantage de contexte de tendance.

### Pas de base de données
La persistance locale reste légère :
- watchlist en JSON
- pas d'historisation utilisateur
- pas d'alertes persistantes

---

## Ce Qui Est Bon À Savoir Pour Développer

### Principes à conserver
- `data.py` pour tout fetching
- `charts.py` pour tout graphique
- `ui.py` pour tout style partagé
- pages séparées dans `pages/`
- `app.py` minimal

### Règles importantes
- toujours gérer `None`, `NaN`, DataFrame vide
- mettre en cache avec `@st.cache_data`
- ne pas faire de logique de données complexe directement dans les pages si elle peut vivre dans `data.py`
- garder l'interface lisible avant de la rendre plus “riche”

### Philosophie produit
Le but n'est pas de faire une app “jolie mais vide”.
Chaque bloc doit répondre à une question d'investisseur :
- le titre est-il cher ou bon marché ?
- la qualité est-elle bonne ?
- le marché est-il risk-on ou risk-off ?
- le momentum est-il favorable ?
- la thèse est-elle soutenue par les fondamentaux et le prix ?

---

## Roadmap Priorisée

### Priorité 1 — Très utile
- ajouter top gainers / losers sur `Market Overview`
- ajouter vrai put/call ratio si source fiable disponible
- ajouter calendar macro (Fed, CPI, NFP)
- ajouter upcoming earnings de grandes caps
- enrichir `Stock Analysis` avec comparaison de peers

### Priorité 2 — Forte valeur analytique
- ajouter export CSV au screener
- ajouter univers prédéfinis : S&P 500, Nasdaq 100, custom
- ajouter radar chart de comparaison
- ajouter heatmap sectorielle / facteurs
- ajouter signaux techniques plus propres dans `Market Overview`

### Priorité 3 — Qualité de vie
- alertes simples sur watchlist
- champs sauvegardés par session
- meilleure gestion des erreurs réseau
- messages utilisateur plus explicites

### Priorité 4 — Niveau supérieur
- intégration FRED pour données macro propres
- vraie base SQLite
- moteur d'alertes
- partage externe / déploiement web
- génération de synthèse IA structurée

---

## Idées D'Amélioration Par Page

### Stock Analysis
À ajouter ou améliorer :
- peers comparables
- résumé d'investissement
- thèse bull / bear / risques
- qualité du cash-flow
- historique multi-années plus propre
- ownership institutionnel si source fiable

### Market Overview
À ajouter ou améliorer :
- put/call ratio
- top movers
- suivi earnings hebdo
- calendrier macro
- breadth plus institutionnel
- crédit / high yield spread
- commodities supplémentaires

### Screener
À ajouter ou améliorer :
- presets d'univers
- tri plus riche
- export CSV
- plus de filtres fondamentaux et techniques
- sauvegarde de screens

### Relative Performance
À ajouter ou améliorer :
- rolling z-score
- corrélation
- spread bands
- export image / rapport simple

### Watchlist
À ajouter ou améliorer :
- colonnes personnalisables
- alertes de prix
- classement automatique
- tags / notes personnelles

---

## Si On Veut Partager L'Outil Plus Tard

Techniquement faisable :
- déploiement Streamlit sur un serveur
- URL publique
- domaine

Mais avant cela il faudrait :
- renforcer la robustesse
- clarifier les dépendances de données
- sécuriser les sources externes
- gérer la montée en charge minimale

---

## Comment Travailler Sur Le Projet

Quand on modifie l'outil :
- avancer feature par feature
- garder le projet simple
- tester systématiquement le lancement
- vérifier les pages une par une
- privilégier une logique explicable plutôt qu'une “boîte noire”

Ce projet doit rester :
- pédagogique
- utilisable
- maintenable

---

## Résumé

Le projet n'est plus une simple base Streamlit.
C'est maintenant une application locale multi-pages structurée, avec :
- navigation latérale
- vraie page stock
- vrai cockpit marché
- screener
- comparaison relative
- watchlist
- thème visuel cohérent
- lancement local propre sans process caché en fond

Les prochaines améliorations les plus importantes sont surtout du côté :
- profondeur de données marché
- comparaison de peers
- calendrier macro / earnings
- signaux plus institutionnels
