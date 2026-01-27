#!/usr/bin/env python3
"""
Génère le README.md principal avec la dernière veille tech.
Utilisé par GitHub Actions pour mettre à jour automatiquement le repo.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Dossier de sortie des veilles
OUTPUT_DIR = Path(__file__).parent.parent / "output"
README_PATH = Path(__file__).parent.parent / "README.md"


def get_latest_watch_file() -> Path | None:
    """Trouve le fichier de veille le plus récent."""
    if not OUTPUT_DIR.exists():
        return None
    
    watch_files = list(OUTPUT_DIR.glob("veille_*.md"))
    if not watch_files:
        return None
    
    # Trier par date (nom de fichier)
    watch_files.sort(reverse=True)
    return watch_files[0]


def get_recent_watches(limit: int = 7) -> list[Path]:
    """Récupère les N dernières veilles."""
    if not OUTPUT_DIR.exists():
        return []
    
    watch_files = list(OUTPUT_DIR.glob("veille_*.md"))
    watch_files.sort(reverse=True)
    return watch_files[:limit]


def generate_readme():
    """Génère le README.md avec la dernière veille."""
    
    latest_file = get_latest_watch_file()
    recent_files = get_recent_watches(7)
    
    # Lire le contenu de la dernière veille
    latest_content = ""
    if latest_file:
        with open(latest_file, "r", encoding="utf-8") as f:
            latest_content = f.read()
    
    # Générer la liste des archives
    archives_list = ""
    if recent_files:
        for f in recent_files:
            date_str = f.stem.replace("veille_", "")
            archives_list += f"- [{date_str}](output/{f.name})\n"
    
    # Template du README
    readme_content = f'''# 🔍 Tech Watch Agent

[![Daily Tech Watch](https://github.com/LovichiDorian/AIAgentTrend/actions/workflows/daily-watch.yml/badge.svg)](https://github.com/LovichiDorian/AIAgentTrend/actions/workflows/daily-watch.yml)

> Agent de veille technologique automatisé basé sur **LangGraph** + **LangChain**.  
> Mis à jour automatiquement chaque jour à 8h UTC.

---

## 📰 Dernière Veille

{latest_content if latest_content else "*Aucune veille disponible. Lancez l'agent manuellement ou attendez la prochaine exécution automatique.*"}

---

## 📚 Archives

{archives_list if archives_list else "*Pas encore d'archives.*"}

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

*Dernière mise à jour: {datetime.now().strftime("%d/%m/%Y %H:%M")} UTC*
'''
    
    # Écrire le README
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print(f"✅ README.md généré avec succès")
    if latest_file:
        print(f"   Dernière veille: {latest_file.name}")
    print(f"   Archives: {len(recent_files)} fichiers")


if __name__ == "__main__":
    generate_readme()
