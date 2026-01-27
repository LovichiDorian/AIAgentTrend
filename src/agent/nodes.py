"""
Nœuds (fonctions) du StateGraph LangGraph.

Chaque nœud prend le state en entrée et retourne les mises à jour du state.
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any
from collections import defaultdict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI

from .state import (
    TechWatchState,
    SourceResult,
    FOCUS_SOURCE_MAPPING,
    PRIORITY_SOURCES,
    SECONDARY_SOURCES
)
from .tools import AVAILABLE_TOOLS

import os

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION LLM
# =============================================================================

def get_llm(provider: str = "auto"):
    """
    Retourne le LLM configuré.
    
    Args:
        provider: 'auto', 'gemini', ou 'mistral'
                  'auto' essaie Gemini d'abord, puis Mistral
    """
    gemini_key = os.getenv("GOOGLE_API_KEY")
    mistral_key = os.getenv("MISTRAL_API_KEY")
    
    if provider == "gemini" or (provider == "auto" and gemini_key):
        if gemini_key:
            return ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                google_api_key=gemini_key,
                temperature=0.3,
                max_output_tokens=4096
            ), "gemini"
    
    if provider == "mistral" or (provider == "auto" and mistral_key):
        if mistral_key:
            return ChatMistralAI(
                model="mistral-small-latest",
                mistral_api_key=mistral_key,
                temperature=0.3,
                max_tokens=4096
            ), "mistral"
    
    return None, None


def get_available_llm_providers() -> list[str]:
    """Retourne la liste des providers LLM disponibles."""
    providers = []
    if os.getenv("GOOGLE_API_KEY"):
        providers.append("gemini")
    if os.getenv("MISTRAL_API_KEY"):
        providers.append("mistral")
    return providers


# =============================================================================
# NŒUD 1: PLANIFICATION
# =============================================================================

async def planning_node(state: TechWatchState) -> dict[str, Any]:
    """
    Nœud de planification: décide quels tools appeler selon la requête.
    
    Analyse la requête utilisateur et le focus pour déterminer:
    - Les sources prioritaires à interroger
    - Les sources secondaires (si budget le permet)
    - Les paramètres de recherche
    
    Returns:
        Mises à jour du state (sources_to_query, priority_sources, etc.)
    """
    logger.info("🎯 Planification de la veille...")
    
    user_query = state.get("user_query", "").lower()
    focus = state.get("focus", "general")
    max_items = state.get("max_items_per_source", 10)
    
    # Déterminer les sources selon le focus
    focus_sources = FOCUS_SOURCE_MAPPING.get(focus, FOCUS_SOURCE_MAPPING["general"])
    
    # Analyser la requête pour ajuster les sources
    # Mots-clés qui influencent le choix des sources
    keywords_ai = ["ia", "ai", "llm", "gpt", "machine learning", "ml", "deep learning"]
    keywords_devops = ["devops", "kubernetes", "k8s", "docker", "cloud", "infra", "sre"]
    keywords_security = ["security", "sécurité", "hack", "vulnerability", "cve"]
    keywords_web = ["web", "frontend", "backend", "react", "vue", "javascript", "typescript"]
    
    # Ajuster le focus si des mots-clés spécifiques sont détectés
    detected_focus = focus
    if any(kw in user_query for kw in keywords_ai):
        detected_focus = "ai"
        focus_sources = FOCUS_SOURCE_MAPPING["ai"]
    elif any(kw in user_query for kw in keywords_devops):
        detected_focus = "devops"
        focus_sources = FOCUS_SOURCE_MAPPING["devops"]
    elif any(kw in user_query for kw in keywords_security):
        detected_focus = "security"
        focus_sources = FOCUS_SOURCE_MAPPING["security"]
    elif any(kw in user_query for kw in keywords_web):
        detected_focus = "web"
        focus_sources = FOCUS_SOURCE_MAPPING["web"]
    
    # Séparer sources prioritaires et secondaires
    priority = [s for s in focus_sources if s in PRIORITY_SOURCES]
    secondary = [s for s in focus_sources if s in SECONDARY_SOURCES]
    
    # Ajouter des sources complémentaires si le focus est général
    if detected_focus == "general" or focus == "all":
        priority = list(set(priority + ["github_trending", "hackernews"]))
        secondary = list(set(secondary + ["producthunt", "tech_news"]))
    
    logger.info(f"   Focus détecté: {detected_focus}")
    logger.info(f"   Sources prioritaires: {priority}")
    logger.info(f"   Sources secondaires: {secondary}")
    
    return {
        "sources_to_query": priority + secondary,
        "priority_sources": priority,
        "secondary_sources": secondary,
        "focus": detected_focus,
        "metadata": {
            **state.get("metadata", {}),
            "planning_completed": True,
            "detected_focus": detected_focus
        }
    }


# =============================================================================
# NŒUD 2: COLLECTE
# =============================================================================

async def collection_node(state: TechWatchState) -> dict[str, Any]:
    """
    Nœud de collecte: interroge toutes les sources planifiées.
    
    Exécute les tools en parallèle pour optimiser le temps.
    Gère les erreurs gracieusement (une source qui échoue n'arrête pas le reste).
    
    Returns:
        Mises à jour du state (source_results, errors)
    """
    logger.info("📥 Collecte des données...")
    
    sources_to_query = state.get("sources_to_query", [])
    priority_sources = state.get("priority_sources", [])
    
    if not sources_to_query:
        logger.warning("   Aucune source à interroger!")
        return {"errors": ["Aucune source configurée pour cette requête"]}
    
    source_results = {}
    errors = list(state.get("errors", []))
    api_calls = 0
    
    # D'abord les sources prioritaires
    async def fetch_source(source_name: str) -> tuple[str, SourceResult]:
        """Récupère les données d'une source."""
        if source_name not in AVAILABLE_TOOLS:
            return source_name, SourceResult(
                source_name=source_name,
                items=[],
                error=f"Tool '{source_name}' non trouvé"
            )
        
        try:
            tool_func = AVAILABLE_TOOLS[source_name]
            items = await tool_func()
            logger.info(f"   ✓ {source_name}: {len(items)} items")
            return source_name, SourceResult(
                source_name=source_name,
                items=items
            )
        except Exception as e:
            error_msg = f"Erreur {source_name}: {str(e)}"
            logger.warning(f"   ✗ {error_msg}")
            return source_name, SourceResult(
                source_name=source_name,
                items=[],
                error=error_msg
            )
    
    # Exécuter les sources prioritaires d'abord
    logger.info("   Sources prioritaires...")
    priority_tasks = [fetch_source(s) for s in priority_sources if s in sources_to_query]
    priority_results = await asyncio.gather(*priority_tasks)
    
    for source_name, result in priority_results:
        source_results[source_name] = result
        api_calls += 1
        if result.error:
            errors.append(result.error)
    
    # Puis les sources secondaires
    secondary_sources = [s for s in sources_to_query if s not in priority_sources]
    if secondary_sources:
        logger.info("   Sources secondaires...")
        secondary_tasks = [fetch_source(s) for s in secondary_sources]
        secondary_results = await asyncio.gather(*secondary_tasks)
        
        for source_name, result in secondary_results:
            source_results[source_name] = result
            api_calls += 1
            if result.error:
                errors.append(result.error)
    
    total_items = sum(len(r.items) for r in source_results.values())
    logger.info(f"   Total: {total_items} items collectés depuis {len(source_results)} sources")
    
    return {
        "source_results": source_results,
        "errors": errors,
        "total_api_calls": state.get("total_api_calls", 0) + api_calls
    }


# =============================================================================
# NŒUD 3: FILTRAGE & DÉDUPLICATION
# =============================================================================

async def filtering_node(state: TechWatchState) -> dict[str, Any]:
    """
    Nœud de filtrage: déduplique et priorise les items collectés.
    
    - Supprime les doublons (même URL ou titre très similaire)
    - Filtre le contenu trop promotionnel
    - Trie par pertinence (score, engagement, fraîcheur)
    - Limite le nombre total pour économiser les tokens LLM
    
    Returns:
        Mises à jour du state (filtered_items, deduplicated_count)
    """
    logger.info("🔍 Filtrage et déduplication...")
    
    source_results = state.get("source_results", {})
    max_items = state.get("max_items_per_source", 10)
    
    # Agréger tous les items
    all_items = []
    for source_name, result in source_results.items():
        if isinstance(result, SourceResult):
            items = result.items
        elif isinstance(result, dict):
            items = result.get("items", [])
        else:
            continue
        
        for item in items:
            item["_source"] = source_name
            all_items.append(item)
    
    logger.info(f"   Items bruts: {len(all_items)}")
    
    # Déduplication par URL
    seen_urls = set()
    seen_titles = set()
    unique_items = []
    
    for item in all_items:
        url = item.get("url", "")
        title = item.get("title", "").lower().strip()
        
        # Hash du titre pour comparaison approximative
        title_hash = hashlib.md5(title[:50].encode()).hexdigest()[:8]
        
        if url and url not in seen_urls and title_hash not in seen_titles:
            seen_urls.add(url)
            seen_titles.add(title_hash)
            unique_items.append(item)
    
    deduplicated_count = len(all_items) - len(unique_items)
    logger.info(f"   Doublons supprimés: {deduplicated_count}")
    
    # Filtrage du contenu promotionnel (heuristiques simples)
    promo_keywords = [
        "sponsored", "ad:", "[ad]", "promotion", "buy now",
        "discount", "coupon", "deal:", "sale:"
    ]
    
    filtered_items = []
    for item in unique_items:
        title = item.get("title", "").lower()
        if not any(kw in title for kw in promo_keywords):
            filtered_items.append(item)
    
    promo_filtered = len(unique_items) - len(filtered_items)
    if promo_filtered:
        logger.info(f"   Contenu promo filtré: {promo_filtered}")
    
    # Scoring et tri
    def compute_score(item: dict) -> float:
        """Calcule un score de pertinence pour un item."""
        score = 0.0
        
        # Engagement (upvotes, stars, comments)
        score += min(item.get("score", 0) / 100, 10)  # Cap à 10
        score += min(item.get("num_comments", 0) / 50, 5)  # Cap à 5
        
        # Bonus pour certaines sources (haute qualité)
        source = item.get("_source", "")
        if source in ["hackernews", "lobsters"]:
            score += 3
        elif source == "github_trending":
            score += 4
        elif "reddit" in source:
            score += 2
        
        # Pénalité si pas de description
        if not item.get("description") and not item.get("selftext") and not item.get("summary"):
            score -= 1
        
        return score
    
    for item in filtered_items:
        item["_relevance_score"] = compute_score(item)
    
    # Trier par score décroissant
    filtered_items.sort(key=lambda x: x.get("_relevance_score", 0), reverse=True)
    
    # Limiter le nombre total (pour économiser les tokens LLM)
    max_total_items = max_items * 5  # 5x le max par source
    if len(filtered_items) > max_total_items:
        filtered_items = filtered_items[:max_total_items]
        logger.info(f"   Limité à {max_total_items} items (top pertinence)")
    
    # Séparer nouveaux items et déjà vus (pour éviter doublons email)
    new_items = filtered_items
    seen_items = []
    
    try:
        from history_tracker import separate_new_and_seen
        new_items, seen_items = separate_new_and_seen(filtered_items)
        logger.info(f"   Nouveaux items: {len(new_items)}")
        logger.info(f"   Déjà vus (rappels): {len(seen_items)}")
    except ImportError:
        logger.warning("   history_tracker non disponible, tous les items traités comme nouveaux")
    
    logger.info(f"   Items finaux: {len(filtered_items)}")
    
    return {
        "filtered_items": filtered_items,  # Tous les items pour le README
        "new_items": new_items,             # Nouveaux pour l'email
        "seen_items": seen_items,           # Déjà vus (rappels)
        "deduplicated_count": deduplicated_count,
        "metadata": {
            **state.get("metadata", {}),
            "filtering_completed": True,
            "items_before_filter": len(all_items),
            "items_after_filter": len(filtered_items),
            "new_items_count": len(new_items),
            "seen_items_count": len(seen_items)
        }
    }


# =============================================================================
# NŒUD 4: SYNTHÈSE LLM
# =============================================================================

SYNTHESIS_SYSTEM_PROMPT = """Tu es un assistant de veille technologique expert.
Tu dois synthétiser les informations collectées pour un développeur/ingénieur full-stack, DevOps ou IA.

RÈGLES STRICTES:
- Utilise UNIQUEMENT les informations fournies dans les données
- Ne jamais inventer de liens, noms d'outils ou statistiques
- Si une information n'est pas dans les données, ne l'inclus pas
- Reste factuel, pas de hype exagérée
- Français avec termes techniques en anglais
- Phrases courtes et directes
- TOUJOURS inclure les URLs des sources entre parenthèses ou en lien markdown
- Si des items sont marqués [RAPPEL], ils ont déjà été mentionnés les jours précédents mais restent populaires

FORMAT DE RÉPONSE OBLIGATOIRE:

## 🎯 Vue d'ensemble
- [3-5 points clés des grandes tendances/annonces, avec lien vers la source principale]

## 🆕 Nouveautés de la semaine

### 🛠️ Outils & Projets Dev
[3-10 entrées max, format:]
- **[Nom]** ([langage/stack]) - [1 phrase contexte technique] → [pourquoi c'est intéressant]
  🔗 [URL du repo/projet]

### 📰 Articles & Discussions
[Liste des articles/posts importants avec:]
- **[Titre]** ([source]) - [1-2 phrases résumé du problème/angle technique]
  🔗 [URL de l'article]

### 🤖 IA / Data / Infra
[Mises à jour notables: nouveaux modèles, frameworks, annonces cloud, pricing]
  🔗 [URLs des sources]

## 🔄 Rappels (toujours populaires)
[Items déjà mentionnés les jours précédents mais qui restent dans le top - à consulter si pas encore fait]
- **[Nom]** - [Courte description] 🔗 [URL]

## 📚 À creuser
[3-5 recommandations concrètes, OBLIGATOIREMENT avec les liens complets]
- [Titre ou description] → [URL complète]

---
*Sources: [liste des sources utilisées avec leurs URLs principales]*
"""


async def synthesis_node(state: TechWatchState) -> dict[str, Any]:
    """
    Nœud de synthèse: génère la réponse finale via LLM.
    
    Stratégie pour économiser les tokens:
    1. Résumé hiérarchique (par catégorie puis global)
    2. Sélection des items les plus pertinents
    3. Formatage compact des données avant envoi au LLM
    
    Returns:
        Mises à jour du state (synthesis, section_summaries)
    """
    logger.info("✍️ Génération de la synthèse...")
    
    filtered_items = state.get("filtered_items", [])
    new_items = state.get("new_items", filtered_items)  # Nouveaux items
    seen_items = state.get("seen_items", [])  # Items déjà vus (rappels)
    user_query = state.get("user_query", "Quoi de neuf en tech ?")
    focus = state.get("focus", "general")
    errors = state.get("errors", [])
    
    if not filtered_items:
        return {
            "synthesis": "❌ Aucune donnée collectée. Vérifiez la configuration des sources.",
            "completed_at": datetime.now()
        }
    
    # Organiser les NOUVEAUX items par catégorie
    categories = {
        "tools": [],      # GitHub, Product Hunt, DevHunt
        "articles": [],   # HN, Reddit, Lobsters, Tech News
        "ai_data": [],    # ArXiv, Reddit ML, contenus IA
        "videos": []      # YouTube
    }
    
    # Catégorie séparée pour les rappels
    recalls = []
    
    source_category_map = {
        "github_trending": "tools",
        "producthunt": "tools",
        "devhunt": "tools",
        "hackernews": "articles",
        "lobsters": "articles",
        "tech_news": "articles",
        "reddit_programming": "articles",
        "reddit_webdev": "articles",
        "reddit_devops": "articles",
        "reddit_selfhosted": "articles",
        "reddit_netsec": "articles",
        "reddit_ml": "ai_data",
        "reddit_llm": "ai_data",
        "arxiv_ai": "ai_data",
        "youtube_tech": "videos",
        "web_search": "articles",
        "web_search_ddg": "articles"
    }
    
    # Classer les NOUVEAUX items
    for item in new_items:
        source = item.get("_source", "")
        category = source_category_map.get(source, "articles")
        categories[category].append(item)
    
    # Les items déjà vus vont dans les rappels (limité à 10)
    recalls = seen_items[:10]
    
    # Limiter chaque catégorie pour économiser les tokens
    max_per_category = 15
    for cat in categories:
        if len(categories[cat]) > max_per_category:
            categories[cat] = categories[cat][:max_per_category]
    
    # Formater les données pour le LLM (format compact)
    def format_items_for_llm(items: list[dict], category: str) -> str:
        """Formate une liste d'items de façon compacte."""
        if not items:
            return "[Aucune donnée]"
        
        lines = []
        for i, item in enumerate(items, 1):
            title = item.get("title", item.get("name", "Sans titre"))
            url = item.get("url", "")
            source = item.get("_source", "")
            
            # Infos additionnelles selon la catégorie
            extra = ""
            if category == "tools":
                lang = item.get("language", "")
                stars = item.get("total_stars", item.get("period_stars", ""))
                desc = item.get("description", item.get("tagline", ""))[:100]
                extra = f" | {lang}" if lang else ""
                extra += f" | ⭐{stars}" if stars else ""
                extra += f" | {desc}" if desc else ""
            elif category in ["articles", "ai_data"]:
                score = item.get("score", 0)
                comments = item.get("num_comments", 0)
                summary = item.get("summary", item.get("selftext", ""))[:150]
                extra = f" | 👍{score}" if score else ""
                extra += f" | 💬{comments}" if comments else ""
                extra += f" | {summary}" if summary else ""
            
            lines.append(f"{i}. [{source}] {title}{extra}")
            if url:
                lines.append(f"   URL: {url}")
        
        return "\n".join(lines)
    
    # Construire le prompt
    data_section = f"""
## Données collectées - NOUVEAUTÉS

### 🛠️ Outils & Projets (GitHub, Product Hunt, etc.)
{format_items_for_llm(categories['tools'], 'tools')}

### 📰 Articles & Discussions (HN, Reddit, Lobsters, News)
{format_items_for_llm(categories['articles'], 'articles')}

### 🤖 IA / Data (ArXiv, Reddit ML)
{format_items_for_llm(categories['ai_data'], 'ai_data')}

### 🎥 Vidéos (YouTube)
{format_items_for_llm(categories['videos'], 'videos')}

## 🔄 RAPPELS (déjà mentionnés les jours précédents, toujours populaires)
{format_items_for_llm(recalls, 'articles') if recalls else "[Aucun rappel cette semaine]"}
"""
    
    # Ajouter les infos sur les erreurs si pertinent
    error_section = ""
    if errors:
        # Convertir en liste pour pouvoir slicer
        unique_errors = list(set(errors))[:5]
        error_section = f"\n⚠️ Sources indisponibles: {', '.join(unique_errors)}\n"
    
    user_prompt = f"""Requête utilisateur: "{user_query}"
Focus: {focus}
Date: {datetime.now().strftime('%d/%m/%Y')}
{error_section}
{data_section}

Génère une synthèse de veille tech structurée selon le format demandé.
Base-toi UNIQUEMENT sur les données ci-dessus."""

    # Appel LLM avec fallback entre providers
    providers = get_available_llm_providers()
    
    if not providers:
        logger.warning("   ⚠️ Aucun LLM configuré, mode dégradé")
        fallback_synthesis = generate_fallback_synthesis(categories, errors)
        return {
            "synthesis": fallback_synthesis,
            "errors": state.get("errors", []) + ["Aucun LLM configuré"],
            "section_summaries": {
                "tools_count": len(categories["tools"]),
                "articles_count": len(categories["articles"]),
                "ai_data_count": len(categories["ai_data"]),
                "videos_count": len(categories["videos"])
            },
            "completed_at": datetime.now()
        }
    
    messages = [
        SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt)
    ]
    
    last_error = None
    for provider in providers:
        try:
            llm, provider_name = get_llm(provider)
            if not llm:
                continue
                
            logger.info(f"   Appel LLM ({provider_name}) en cours...")
            response = await llm.ainvoke(messages)
            synthesis = response.content
            
            logger.info(f"   ✓ Synthèse générée via {provider_name}")
            
            return {
                "synthesis": synthesis,
                "section_summaries": {
                    "tools_count": len(categories["tools"]),
                    "articles_count": len(categories["articles"]),
                    "ai_data_count": len(categories["ai_data"]),
                    "videos_count": len(categories["videos"])
                },
                "total_api_calls": state.get("total_api_calls", 0) + 1,
                "completed_at": datetime.now(),
                "metadata": {
                    **state.get("metadata", {}),
                    "llm_provider": provider_name
                }
            }
            
        except Exception as e:
            last_error = str(e)
            logger.warning(f"   ⚠️ {provider} échoué: {last_error[:100]}...")
            # Essayer le provider suivant
            continue
    
    # Tous les providers ont échoué
    error_msg = f"Tous les LLMs ont échoué. Dernière erreur: {last_error}"
    logger.error(f"   ✗ {error_msg}")
    
    # Fallback: générer un résumé basique sans LLM
    fallback_synthesis = generate_fallback_synthesis(categories, errors)
    
    return {
        "synthesis": fallback_synthesis,
        "errors": state.get("errors", []) + [error_msg],
        "section_summaries": {
            "tools_count": len(categories["tools"]),
            "articles_count": len(categories["articles"]),
            "ai_data_count": len(categories["ai_data"]),
            "videos_count": len(categories["videos"])
        },
        "completed_at": datetime.now()
    }


def generate_fallback_synthesis(categories: dict, errors: list) -> str:
    """Génère une synthèse basique sans LLM (fallback)."""
    
    lines = ["# 📊 Veille Tech (Mode dégradé - sans LLM)\n"]
    
    if errors:
        unique_errors = list(set(str(e)[:50] for e in errors))[:3]
        lines.append(f"⚠️ Erreurs: {', '.join(unique_errors)}\n")
    
    # Section Outils/Projets
    tools = categories.get("tools", [])
    if tools:
        lines.append("## 🛠️ Top Outils/Projets\n")
        for item in tools[:8]:
            name = item.get("name", item.get("title", "?"))
            url = item.get("url", "")
            lang = item.get("language", "")
            desc = item.get("description", item.get("tagline", ""))[:80]
            stars = item.get("total_stars", item.get("period_stars", ""))
            
            line = f"- **{name}**"
            if lang:
                line += f" ({lang})"
            if stars:
                line += f" ⭐{stars}"
            if desc:
                line += f" - {desc}"
            if url:
                line += f"\n  → {url}"
            lines.append(line)
    
    # Section Articles/Discussions
    articles = categories.get("articles", [])
    if articles:
        lines.append("\n## 📰 Top Articles/Discussions\n")
        for item in articles[:10]:
            title = item.get("title", "?")[:80]
            url = item.get("url", "")
            score = item.get("score", 0)
            source = item.get("_source", item.get("source_name", ""))
            comments = item.get("num_comments", 0)
            
            line = f"- **{title}**"
            if source:
                line += f" [{source}]"
            if score:
                line += f" 👍{score}"
            if comments:
                line += f" 💬{comments}"
            if url:
                line += f"\n  → {url}"
            lines.append(line)
    
    # Section IA/Data
    ai_data = categories.get("ai_data", [])
    if ai_data:
        lines.append("\n## 🤖 IA/Data\n")
        for item in ai_data[:5]:
            title = item.get("title", "?")[:80]
            url = item.get("url", "")
            source = item.get("_source", "")
            
            line = f"- {title}"
            if source:
                line += f" [{source}]"
            if url:
                line += f"\n  → {url}"
            lines.append(line)
    
    # Section Vidéos
    videos = categories.get("videos", [])
    if videos:
        lines.append("\n## 🎥 Vidéos\n")
        for item in videos[:3]:
            title = item.get("title", "?")[:60]
            channel = item.get("channel", "")
            url = item.get("url", "")
            
            line = f"- {title}"
            if channel:
                line += f" ({channel})"
            if url:
                line += f"\n  → {url}"
            lines.append(line)
    
    lines.append("\n---\n*Synthèse générée en mode dégradé (LLM indisponible ou quota dépassé)*")
    lines.append("*💡 Astuce: Configurez MISTRAL_API_KEY comme backup dans .env*")
    
    return "\n".join(lines)


# =============================================================================
# NŒUD FINAL: FORMATAGE
# =============================================================================

async def output_node(state: TechWatchState) -> dict[str, Any]:
    """
    Nœud final: prépare la sortie et les métadonnées finales.
    """
    logger.info("📤 Finalisation...")
    
    synthesis = state.get("synthesis", "")
    new_items = state.get("new_items", [])
    seen_items = state.get("seen_items", [])
    
    # Marquer les nouveaux items comme envoyés dans l'historique
    try:
        from history_tracker import mark_items_as_sent
        mark_items_as_sent(new_items)
        logger.info(f"   {len(new_items)} items marqués comme envoyés")
    except ImportError:
        pass
    
    # Ajouter un footer avec les stats
    stats = state.get("section_summaries", {})
    api_calls = state.get("total_api_calls", 0)
    errors = state.get("errors", [])
    
    footer = f"""

---
📊 **Stats**: {stats.get('tools_count', 0)} outils | {stats.get('articles_count', 0)} articles | {stats.get('ai_data_count', 0)} IA/data | {stats.get('videos_count', 0)} vidéos
🆕 **Nouveautés**: {len(new_items)} | 🔄 **Rappels**: {len(seen_items)}
🔄 **Appels API**: {api_calls}
"""
    
    if errors:
        footer += f"⚠️ **Erreurs**: {len(errors)} source(s) indisponible(s)\n"
    
    return {
        "synthesis": synthesis + footer,
        "completed_at": datetime.now(),
        "metadata": {
            **state.get("metadata", {}),
            "completed": True,
            "total_items_processed": len(state.get("filtered_items", [])),
            "new_items_count": len(new_items),
            "seen_items_count": len(seen_items),
            "total_api_calls": api_calls,
            "error_count": len(errors)
        }
    }
