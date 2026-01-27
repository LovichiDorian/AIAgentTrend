# 🔍 Tech Watch Agent

Agent de veille technologique automatisé basé sur **LangGraph** + **LangChain**, conçu pour tourner sur un VPS modeste (k3s, Oracle Cloud Free Tier).

## 🎯 Objectif

L'agent collecte, filtre et synthétise les actualités tech de multiples sources pour un développeur/ingénieur full-stack, DevOps ou IA.

**Caractéristiques clés:**

- 📡 Multi-sources: GitHub Trending, Hacker News, Reddit, Lobste.rs, Tech News RSS, YouTube, Product Hunt...
- 🤖 Synthèse LLM: Gemini ou Mistral (free tier)
- ⚡ Sobre en ressources: Optimisé pour VPS modeste
- 🐳 Containerisé: Docker + manifests Kubernetes (k3s)

## 📁 Structure du projet

```
AIAGENTTREND/
├── src/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py      # State LangGraph
│   │   ├── tools.py      # Tools LangChain (sources)
│   │   ├── nodes.py      # Nœuds du graph
│   │   └── graph.py      # Construction StateGraph
│   ├── config.py         # Configuration centralisée
│   └── main.py           # Point d'entrée CLI/HTTP
├── k8s/
│   ├── deployment.yaml   # Deployment Kubernetes
│   └── service.yaml      # Service + Ingress + CronJob
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 Démarrage rapide

### 1. Configuration

```bash
# Cloner et accéder au projet
cd AIAGENTTREND

# Copier le template de configuration
cp .env.example .env

# Éditer .env avec vos clés API
# Au minimum: GOOGLE_API_KEY ou MISTRAL_API_KEY
```

### 2. Installation locale

```bash
# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: .\venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### 3. Exécution

**Mode CLI:**

```bash
cd src

# Veille générale
python main.py "Quoi de neuf en tech ?"

# Veille focalisée IA
python main.py --focus ai "Nouveautés LLM"

# Veille DevOps
python main.py --focus devops "Kubernetes et cloud natif"

# Voir le statut de la config
python main.py --status
```

**Mode serveur HTTP:**

```bash
python main.py --serve --port 8080

# Puis dans un navigateur ou curl:
# GET http://localhost:8080/watch?focus=ai
# POST http://localhost:8080/watch avec JSON body
```

## 🐳 Déploiement Docker

```bash
# Build de l'image
docker build -t tech-watch-agent:latest .

# Exécution locale
docker run -d \
  --name tech-watch \
  -p 8080:8080 \
  -e GOOGLE_API_KEY=your-key \
  tech-watch-agent:latest
```

## ☸️ Déploiement k3s

```bash
# Créer le secret avec vos clés API
kubectl create secret generic tech-watch-secrets \
  --from-literal=GOOGLE_API_KEY=your-key \
  --from-literal=MISTRAL_API_KEY=your-key

# Déployer
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Vérifier
kubectl get pods -l app=tech-watch-agent
kubectl logs -f deployment/tech-watch-agent
```

## 📡 Sources de données

| Source          | Type                  | API               | Statut         |
| --------------- | --------------------- | ----------------- | -------------- |
| GitHub Trending | Repos populaires      | Scraping          | ✅ Gratuit     |
| Hacker News     | Articles/discussions  | API publique      | ✅ Gratuit     |
| Reddit          | Subreddits tech       | API JSON publique | ✅ Gratuit     |
| Lobste.rs       | Articles dev          | API JSON          | ✅ Gratuit     |
| Tech News RSS   | TechCrunch, Ars, etc. | RSS feeds         | ✅ Gratuit     |
| Product Hunt    | Nouveaux produits     | Scraping          | ⚠️ Limité      |
| YouTube         | Vidéos tech           | API v3            | 🔑 Clé requise |
| Web Search      | Recherche générale    | SerpAPI/DDG       | 🔑 Optionnel   |
| ArXiv           | Papers IA/ML          | RSS               | ✅ Gratuit     |

## 🏗️ Architecture LangGraph

```
[START]
   │
   ▼
┌─────────┐
│ Planning│  ← Analyse la requête, décide les sources
└────┬────┘
     │
     ▼
┌──────────┐
│Collection│  ← Appelle les tools en parallèle
└────┬─────┘
     │
     ▼
┌──────────┐
│ Filtering│  ← Déduplique, filtre, priorise
└────┬─────┘
     │
     ▼
┌──────────┐
│ Synthesis│  ← Génère la synthèse via LLM
└────┬─────┘
     │
     ▼
┌────────┐
│ Output │   ← Formate la sortie finale
└────┬───┘
     │
     ▼
  [END]
```

## ⚙️ Optimisations ressources

L'agent est conçu pour tourner sur un VPS modeste:

- **Appels LLM minimisés**: Résumé hiérarchique, un seul appel final
- **Requêtes parallèles**: Collecte simultanée des sources
- **Déduplication**: Évite les doublons avant synthèse
- **Limites configurables**: `max_items_per_source`, timeouts
- **Fallback gracieux**: Continue si une source échoue
- **Ressources Kubernetes**: Requests/limits adaptés (128Mi-512Mi RAM)

## 📝 Format de sortie

```markdown
## 🎯 Vue d'ensemble

- Point clé 1
- Point clé 2
- ...

## 🛠️ Outils & Projets Dev

- **Nom** (langage) - Contexte → Intérêt

## 📰 Articles & Discussions

- **Titre** (source) - Résumé

## 🤖 IA / Data / Infra

- Mises à jour notables...

## 📚 À creuser

- Recommandations concrètes
```

## 🔑 Variables d'environnement

| Variable          | Requis | Description                   |
| ----------------- | ------ | ----------------------------- |
| `GOOGLE_API_KEY`  | ⚠️     | Clé API Gemini                |
| `MISTRAL_API_KEY` | ⚠️     | Clé API Mistral (alternative) |
| `YOUTUBE_API_KEY` | ❌     | YouTube Data API v3           |
| `SERPAPI_KEY`     | ❌     | Recherche web avancée         |
| `DEBUG`           | ❌     | Mode debug (true/false)       |
| `LOG_LEVEL`       | ❌     | Niveau de log (INFO)          |
| `HTTP_PORT`       | ❌     | Port serveur (8080)           |

## 📜 License

MIT

## 🤝 Contribution

Les PRs sont bienvenues! Priorités:

- Nouvelles sources de données
- Amélioration du filtrage/scoring
- Optimisations performance
- Tests unitaires

python main.py "Quoi de neuf en tech ?" -o auto
