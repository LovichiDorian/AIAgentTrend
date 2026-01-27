# 🔍 Tech Watch Agent

[![Daily Tech Watch](https://github.com/LovichiDorian/AIAgentTrend/actions/workflows/daily-watch.yml/badge.svg)](https://github.com/LovichiDorian/AIAgentTrend/actions/workflows/daily-watch.yml)

> Agent de veille technologique automatisé basé sur **LangGraph** + **LangChain**.  
> Mis à jour automatiquement chaque jour à 8h UTC.

---

## 📰 Dernière Veille

# 🔍 Veille Tech - 27/01/2026 09:52

**Requête:** Veille tech quotidienne
**Focus:** general

---

## 🎯 Vue d'ensemble
- Apple lance une nouvelle version d'AirTag avec une portée étendue et une meilleure détection (https://www.apple.com/newsroom/2026/01/apple-introduces-new-airtag-with-expanded-range-and-improved-findability/)
- ChatGPT Containers gagne des fonctionnalités avancées comme l'exécution de bash et l'installation de packages (https://simonwillison.net/2026/Jan/26/chatgpt-containers/)
- Heathrow supprime la limite de taille des contenants de liquide en cabine (https://www.bbc.com/news/articles/c1evvx89559o)
- Windows 11 rencontre des problèmes majeurs avec sa mise à jour Patch Tuesday (https://www.windowscentral.com/microsoft/windows-11/windows-11s-botched-patch-tuesday-update-nightmare-continues-as-microsoft-confirms-some-pcs-might-fail-to-boot)
- Discussion sur la bulle des outils d'AI code review (https://www.greptile.com/blog/ai-code-review-bubble)

## 🛠️ Outils & Projets Dev
- **[Remotion]** (TypeScript) - Création de vidéos programmatiques avec React → Idéal pour les développeurs voulant automatiser la production vidéo
  🔗 https://github.com/remotion-dev/remotion
- **[zerobrew]** (Rust) - Alternative à Homebrew 5-20x plus rapide → Solution intéressante pour les utilisateurs macOS cherchant des performances
  🔗 https://github.com/lucasgelfond/zerobrew

## 📰 Articles & Discussions
- **[Apple introduces new AirTag with longer range and improved findability]** (HackerNews) - Nouvelle version avec meilleure portée et détection
  🔗 https://www.apple.com/newsroom/2026/01/apple-introduces-new-airtag-with-expanded-range-and-improved-findability/
- **[ChatGPT Containers can now run bash, pip/npm install packages and download files]** (HackerNews) - Fonctionnalités avancées ajoutées aux containers ChatGPT
  🔗 https://simonwillison.net/2026/Jan/26/chatgpt-containers/
- **[Heathrow scraps liquid container limit]** (HackerNews) - Suppression de la limite de taille des contenants de liquide en cabine
  🔗 https://www.bbc.com/news/articles/c1evvx89559o
- **[Windows 11's Patch Tuesday nightmare gets worse]** (HackerNews) - Problèmes majeurs avec la mise à jour Patch Tuesday de Windows 11
  🔗 https://www.windowscentral.com/microsoft/windows-11/windows-11s-botched-patch-tuesday-update-nightmare-continues-as-microsoft-confirms-some-pcs-might-fail-to-boot
- **[There is an AI code review bubble]** (HackerNews) - Discussion sur la surévaluation des outils d'AI code review
  🔗 https://www.greptile.com/blog/ai-code-review-bubble

## 🤖 IA / Data / Infra
[Aucune donnée]

## 📚 À creuser
- [The hidden engineering of runways] → https://practical.engineering/blog/2026/1/20/the-hidden-engineering-of-runways
- [The state of Linux music players in 2026] → https://crescentro.se/posts/linux-music-players-2026/
- [The Enclosure feedback loop, or how LLMs sabotage existing programming practices by privatizing a public good] → https://michiel.buddingh.eu/enclosure-feedback-loop

*Sources: [https://www.apple.com/newsroom/2026/01/apple-introduces-new-airtag-with-expanded-range-and-improved-findability/, https://simonwillison.net/2026/Jan/26/chatgpt-containers/, https://www.bbc.com/news/articles/c1evvx89559o, https://www.windowscentral.com/microsoft/windows-11/windows-11s-botched-patch-tuesday-update-nightmare-continues-as-microsoft-confirms-some-pcs-might-fail-to-boot, https://www.greptile.com/blog/ai-code-review-bubble, https://github.com/remotion-dev/remotion, https://github.com/lucasgelfond/zerobrew, https://practical.engineering/blog/2026/1/20/the-hidden-engineering-of-runways, https://crescentro.se/posts/linux-music-players-2026/, https://michiel.buddingh.eu/enclosure-feedback-loop]*

---
📊 **Stats**: 1 outils | 15 articles | 0 IA/data | 0 vidéos
🔄 **Appels API**: 7


---

## 📚 Archives

- [2026-01-27](output/veille_2026-01-27.md)


---

## 🤖 À propos de cet agent

### Sources de données
| Source | Description |
|--------|-------------|
| 🐙 GitHub Trending | Repos populaires de la semaine |
| 🔶 Hacker News | Top stories tech |
| 🦞 Lobste.rs | Articles dev/tech |
| 🔴 Reddit | r/programming, r/MachineLearning, r/devops... |
| 📰 Tech News RSS | TechCrunch, Ars Technica, The Verge, Wired |
| 🎥 YouTube | Vidéos tech récentes (si API configurée) |
| 🚀 Product Hunt | Nouveaux produits/outils |

### Stack technique
- **Orchestration**: LangGraph (StateGraph)
- **LLM**: Gemini 2.0 Flash / Mistral (fallback)
- **Sources**: APIs publiques + scraping léger
- **Déploiement**: GitHub Actions (quotidien) / Docker / k3s

### Exécution manuelle

```bash
# Cloner le repo
git clone https://github.com/LovichiDorian/AIAgentTrend.git
cd AIAgentTrend

# Installer les dépendances
pip install -r requirements.txt

# Configurer les clés API
cp .env.example .env
# Éditer .env avec GOOGLE_API_KEY ou MISTRAL_API_KEY

# Lancer une veille
cd src
python main.py "Quoi de neuf en tech ?" -o auto
```

### Options CLI

```bash
# Focus thématique
python main.py --focus ai "Nouveautés LLM"
python main.py --focus devops "Kubernetes"
python main.py --focus security "Vulnérabilités récentes"

# Sauvegarder le résultat
python main.py "Veille" -o auto                    # veille_YYYY-MM-DD.md
python main.py "Veille" -o mon_fichier             # mon_fichier.md

# Mode serveur HTTP
python main.py --serve --port 8080
```

---

## 📜 License

MIT

---

*Dernière mise à jour: 27/01/2026 09:52 UTC*
