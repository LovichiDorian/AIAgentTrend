"""
Configuration centralisée pour l'agent de veille.

Toutes les variables sont chargées depuis l'environnement ou un fichier .env.
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Charger le fichier .env s'il existe
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


@dataclass
class LLMConfig:
    """Configuration des LLMs."""
    
    # Clés API
    google_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY")
    )
    mistral_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("MISTRAL_API_KEY")
    )
    
    # Modèles à utiliser
    gemini_model: str = "gemini-2.0-flash"
    mistral_model: str = "mistral-small-latest"
    
    # Paramètres
    temperature: float = 0.3
    max_tokens: int = 4096
    
    @property
    def has_llm(self) -> bool:
        """Vérifie qu'au moins un LLM est configuré."""
        return bool(self.google_api_key or self.mistral_api_key)
    
    @property
    def preferred_provider(self) -> Optional[str]:
        """Retourne le provider LLM préféré (Gemini prioritaire)."""
        if self.google_api_key:
            return "gemini"
        elif self.mistral_api_key:
            return "mistral"
        return None


@dataclass
class SourcesConfig:
    """Configuration des sources de données."""
    
    # Clés API optionnelles
    youtube_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("YOUTUBE_API_KEY")
    )
    serpapi_key: Optional[str] = field(
        default_factory=lambda: os.getenv("SERPAPI_KEY")
    )
    reddit_client_id: Optional[str] = field(
        default_factory=lambda: os.getenv("REDDIT_CLIENT_ID")
    )
    reddit_client_secret: Optional[str] = field(
        default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET")
    )
    
    # Limites par défaut
    default_limit_per_source: int = 10
    max_total_items: int = 100
    
    # Timeouts
    request_timeout: float = 10.0
    max_retries: int = 2
    
    # Subreddits par défaut
    default_subreddits: list[str] = field(default_factory=lambda: [
        "programming",
        "MachineLearning",
        "devops",
        "selfhosted",
        "netsec",
        "webdev",
        "LocalLLaMA"
    ])
    
    @property
    def has_youtube(self) -> bool:
        return bool(self.youtube_api_key)
    
    @property
    def has_serpapi(self) -> bool:
        return bool(self.serpapi_key)


@dataclass  
class AgentConfig:
    """Configuration globale de l'agent."""
    
    # Mode de fonctionnement
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    
    # Limites de ressources (pour VPS modeste)
    max_concurrent_requests: int = 5
    max_llm_calls_per_run: int = 3
    
    # Cache (pour réduire les appels)
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600  # 1 heure
    
    # Serveur HTTP
    http_host: str = field(
        default_factory=lambda: os.getenv("HTTP_HOST", "0.0.0.0")
    )
    http_port: int = field(
        default_factory=lambda: int(os.getenv("HTTP_PORT", "8080"))
    )


@dataclass
class Config:
    """Configuration principale - agrège toutes les configs."""
    
    llm: LLMConfig = field(default_factory=LLMConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    
    def validate(self) -> list[str]:
        """Valide la configuration et retourne les warnings."""
        warnings = []
        
        if not self.llm.has_llm:
            warnings.append(
                "⚠️ Aucun LLM configuré! Définir GOOGLE_API_KEY ou MISTRAL_API_KEY"
            )
        
        if not self.sources.has_youtube:
            warnings.append(
                "ℹ️ YouTube API non configurée - source désactivée"
            )
        
        if not self.sources.has_serpapi:
            warnings.append(
                "ℹ️ SerpAPI non configurée - recherche web limitée (DuckDuckGo)"
            )
        
        return warnings
    
    def print_status(self):
        """Affiche le statut de la configuration."""
        print("=" * 50)
        print("🔧 Configuration Tech Watch Agent")
        print("=" * 50)
        
        # LLM
        print(f"\n📡 LLM Provider: {self.llm.preferred_provider or 'NON CONFIGURÉ'}")
        if self.llm.google_api_key:
            print(f"   ✓ Gemini ({self.llm.gemini_model})")
        if self.llm.mistral_api_key:
            print(f"   ✓ Mistral ({self.llm.mistral_model})")
        
        # Sources
        print(f"\n📥 Sources:")
        print(f"   ✓ Reddit (API publique)")
        print(f"   ✓ GitHub Trending (scraping)")
        print(f"   ✓ Hacker News (API)")
        print(f"   ✓ Lobste.rs (API)")
        print(f"   ✓ Tech News RSS")
        print(f"   {'✓' if self.sources.has_youtube else '✗'} YouTube")
        print(f"   {'✓' if self.sources.has_serpapi else '○'} SerpAPI (DuckDuckGo fallback)")
        
        # Warnings
        warnings = self.validate()
        if warnings:
            print(f"\n⚠️ Warnings:")
            for w in warnings:
                print(f"   {w}")
        
        print("=" * 50)


# Instance globale
config = Config()


def get_config() -> Config:
    """Retourne la configuration globale."""
    return config


def reload_config():
    """Recharge la configuration depuis l'environnement."""
    global config
    load_dotenv(override=True)
    config = Config()
    return config
