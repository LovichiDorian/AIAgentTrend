"""
Définition du State LangGraph pour l'agent de veille technologique.
"""

from typing import TypedDict, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceResult:
    """Résultat d'une source de veille."""
    source_name: str
    items: list[dict]  # Liste d'items (titre, url, score, description, etc.)
    fetched_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now()


class TechWatchState(TypedDict, total=False):
    """
    State principal de l'agent de veille.
    
    Attributs:
        user_query: La requête utilisateur brute
        focus: Focus thématique (general, ai, devops, web, security, etc.)
        period: Période de recherche (today, week, month)
        max_items_per_source: Limite d'items par source pour économiser les ressources
        
        sources_to_query: Liste des sources à interroger (décidée par le planificateur)
        source_results: Résultats bruts par source
        
        filtered_items: Items après dédoublonnage et filtrage
        synthesis: Synthèse finale générée par le LLM
        
        errors: Liste des erreurs rencontrées (sources indisponibles, etc.)
        metadata: Métadonnées diverses (timestamps, stats, etc.)
    """
    # Entrée utilisateur
    user_query: str
    focus: Literal["general", "ai", "devops", "web", "security", "tools", "all"]
    period: Literal["today", "week", "month"]
    max_items_per_source: int
    
    # Planification
    sources_to_query: list[str]
    priority_sources: list[str]  # Sources prioritaires (fort signal)
    secondary_sources: list[str]  # Sources complémentaires
    
    # Collecte
    source_results: dict[str, SourceResult]
    
    # Filtrage
    filtered_items: list[dict]
    deduplicated_count: int
    
    # Synthèse
    synthesis: str
    section_summaries: dict[str, str]  # Résumés par section
    
    # Métadonnées & erreurs
    errors: list[str]
    metadata: dict
    total_api_calls: int
    started_at: datetime
    completed_at: datetime


def create_initial_state(
    user_query: str = "Quoi de neuf en tech ?",
    focus: str = "general",
    period: str = "week",
    max_items_per_source: int = 10
) -> TechWatchState:
    """
    Crée un state initial avec des valeurs par défaut.
    
    Args:
        user_query: Requête utilisateur
        focus: Focus thématique
        period: Période de recherche
        max_items_per_source: Limite d'items par source
        
    Returns:
        State initial prêt à être utilisé par le graph
    """
    return TechWatchState(
        user_query=user_query,
        focus=focus,
        period=period,
        max_items_per_source=max_items_per_source,
        sources_to_query=[],
        priority_sources=[],
        secondary_sources=[],
        source_results={},
        filtered_items=[],
        deduplicated_count=0,
        synthesis="",
        section_summaries={},
        errors=[],
        metadata={
            "version": "1.0.0",
            "agent": "tech-watch-agent"
        },
        total_api_calls=0,
        started_at=datetime.now(),
        completed_at=None
    )


# Mapping des focus vers les sources pertinentes
FOCUS_SOURCE_MAPPING = {
    "general": [
        "github_trending", "hackernews", "reddit_programming",
        "tech_news", "lobsters", "producthunt"
    ],
    "ai": [
        "github_trending", "hackernews", "reddit_ml",
        "reddit_llm", "arxiv_ai", "tech_news_ai"
    ],
    "devops": [
        "github_trending", "reddit_devops", "reddit_selfhosted",
        "hackernews", "tech_news_devops"
    ],
    "web": [
        "github_trending", "reddit_programming", "reddit_webdev",
        "hackernews", "producthunt"
    ],
    "security": [
        "github_trending", "reddit_netsec", "hackernews",
        "tech_news_security"
    ],
    "tools": [
        "github_trending", "producthunt", "devhunt",
        "hackernews", "reddit_selfhosted"
    ],
    "all": [
        "github_trending", "hackernews", "reddit_programming",
        "reddit_ml", "reddit_devops", "lobsters", "producthunt",
        "tech_news", "youtube_tech"
    ]
}

# Sources prioritaires (fort signal, haute qualité)
PRIORITY_SOURCES = [
    "github_trending",
    "hackernews", 
    "reddit_programming",
    "reddit_ml",
    "lobsters"
]

# Sources secondaires (complément)
SECONDARY_SOURCES = [
    "producthunt",
    "devhunt",
    "youtube_tech",
    "web_search"
]
