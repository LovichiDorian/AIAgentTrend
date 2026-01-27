"""
Tools LangChain pour interroger les différentes sources de veille.

Chaque tool est une fonction Python wrappée en tool LangChain.
Les implémentations utilisent des APIs gratuites ou du scraping léger.
"""

import os
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from bs4 import BeautifulSoup
import json
import logging

logger = logging.getLogger(__name__)

# Configuration des timeouts et limites
REQUEST_TIMEOUT = 10.0
MAX_RETRIES = 2
USER_AGENT = "TechWatchAgent/1.0 (Educational purpose)"


# =============================================================================
# UTILITAIRES
# =============================================================================

async def safe_request(
    url: str,
    method: str = "GET",
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: float = REQUEST_TIMEOUT
) -> Optional[httpx.Response]:
    """
    Effectue une requête HTTP avec gestion d'erreurs robuste.
    
    Returns:
        Response ou None si échec
    """
    default_headers = {"User-Agent": USER_AGENT}
    if headers:
        default_headers.update(headers)
    
    async with httpx.AsyncClient() as client:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=default_headers,
                    params=params,
                    timeout=timeout
                )
                response.raise_for_status()
                return response
            except httpx.TimeoutException:
                logger.warning(f"Timeout pour {url} (tentative {attempt + 1})")
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} pour {url}")
                if e.response.status_code == 429:  # Rate limit
                    await asyncio.sleep(2 ** attempt)
                else:
                    break
            except Exception as e:
                logger.error(f"Erreur requête {url}: {e}")
                break
    return None


def parse_relative_time(time_str: str) -> Optional[datetime]:
    """Parse une date relative (ex: '2 hours ago') en datetime."""
    # Implémentation basique
    now = datetime.now()
    if "hour" in time_str:
        hours = int(''.join(filter(str.isdigit, time_str)) or 1)
        return now - timedelta(hours=hours)
    elif "day" in time_str:
        days = int(''.join(filter(str.isdigit, time_str)) or 1)
        return now - timedelta(days=days)
    elif "week" in time_str:
        weeks = int(''.join(filter(str.isdigit, time_str)) or 1)
        return now - timedelta(weeks=weeks)
    return now


# =============================================================================
# REDDIT TOOLS
# =============================================================================

@tool
async def fetch_reddit_subreddit(
    subreddit: str,
    sort: str = "hot",
    limit: int = 10,
    time_filter: str = "week"
) -> list[dict]:
    """
    Récupère les posts récents d'un subreddit via l'API JSON publique.
    
    Args:
        subreddit: Nom du subreddit (ex: 'programming', 'MachineLearning')
        sort: Tri des posts ('hot', 'new', 'top', 'rising')
        limit: Nombre max de posts à récupérer
        time_filter: Filtre temporel pour 'top' ('hour', 'day', 'week', 'month', 'year')
    
    Returns:
        Liste de posts avec titre, url, score, commentaires, etc.
    """
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
    params = {"limit": min(limit, 25), "t": time_filter}
    
    response = await safe_request(url, params=params)
    if not response:
        return []
    
    try:
        data = response.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            posts.append({
                "title": post.get("title", ""),
                "url": post.get("url", ""),
                "permalink": f"https://reddit.com{post.get('permalink', '')}",
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "created_utc": post.get("created_utc", 0),
                "subreddit": subreddit,
                "author": post.get("author", ""),
                "selftext": post.get("selftext", "")[:500],  # Limiter le texte
                "is_self": post.get("is_self", False),
                "source": "reddit"
            })
        return posts
    except Exception as e:
        logger.error(f"Erreur parsing Reddit r/{subreddit}: {e}")
        return []


@tool
async def fetch_reddit_multiple(
    subreddits: list[str],
    sort: str = "hot",
    limit_per_sub: int = 5
) -> list[dict]:
    """
    Récupère les posts de plusieurs subreddits en parallèle.
    Optimisé pour réduire le nombre d'appels.
    
    Args:
        subreddits: Liste de subreddits à interroger
        sort: Tri des posts
        limit_per_sub: Limite par subreddit
    
    Returns:
        Liste agrégée de tous les posts
    """
    tasks = [
        fetch_reddit_subreddit.ainvoke({
            "subreddit": sub,
            "sort": sort,
            "limit": limit_per_sub
        })
        for sub in subreddits
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_posts = []
    for result in results:
        if isinstance(result, list):
            all_posts.extend(result)
        elif isinstance(result, Exception):
            logger.warning(f"Erreur Reddit: {result}")
    
    # Trier par score décroissant
    all_posts.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_posts


# =============================================================================
# GITHUB TRENDING
# =============================================================================

@tool
async def fetch_github_trending(
    language: str = "",
    since: str = "weekly"
) -> list[dict]:
    """
    Récupère les repos trending sur GitHub via scraping léger.
    
    Args:
        language: Filtrer par langage (ex: 'python', 'javascript', '' pour tous)
        since: Période ('daily', 'weekly', 'monthly')
    
    Returns:
        Liste de repos trending avec nom, description, stars, etc.
    """
    url = f"https://github.com/trending/{language}"
    params = {"since": since}
    
    response = await safe_request(url, params=params)
    if not response:
        return []
    
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        repos = []
        
        for article in soup.select("article.Box-row")[:15]:
            # Nom du repo
            h2 = article.select_one("h2 a")
            if not h2:
                continue
            
            repo_path = h2.get("href", "").strip("/")
            repo_name = repo_path.split("/")[-1] if "/" in repo_path else repo_path
            
            # Description
            desc_elem = article.select_one("p")
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            
            # Langage
            lang_elem = article.select_one("[itemprop='programmingLanguage']")
            lang = lang_elem.get_text(strip=True) if lang_elem else "Unknown"
            
            # Stars totales et stars période
            stars_elems = article.select("a.Link--muted")
            total_stars = ""
            if stars_elems:
                total_stars = stars_elems[0].get_text(strip=True)
            
            # Stars gagnées dans la période
            period_stars_elem = article.select_one("span.d-inline-block.float-sm-right")
            period_stars = period_stars_elem.get_text(strip=True) if period_stars_elem else ""
            
            repos.append({
                "name": repo_name,
                "full_name": repo_path,
                "url": f"https://github.com/{repo_path}",
                "description": description[:300],
                "language": lang,
                "total_stars": total_stars,
                "period_stars": period_stars,
                "source": "github_trending"
            })
        
        return repos
    except Exception as e:
        logger.error(f"Erreur parsing GitHub Trending: {e}")
        return []


# =============================================================================
# HACKER NEWS
# =============================================================================

@tool
async def fetch_hackernews(
    story_type: str = "top",
    limit: int = 15
) -> list[dict]:
    """
    Récupère les stories Hacker News via l'API officielle.
    
    Args:
        story_type: Type de stories ('top', 'new', 'best', 'ask', 'show')
        limit: Nombre de stories à récupérer
    
    Returns:
        Liste de stories avec titre, url, score, commentaires
    """
    # Récupérer les IDs des stories
    url = f"https://hacker-news.firebaseio.com/v0/{story_type}stories.json"
    response = await safe_request(url)
    if not response:
        return []
    
    try:
        story_ids = response.json()[:limit]
    except:
        return []
    
    # Récupérer les détails de chaque story (en parallèle, par batch)
    async def fetch_story(story_id: int) -> Optional[dict]:
        url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        resp = await safe_request(url)
        if resp:
            return resp.json()
        return None
    
    tasks = [fetch_story(sid) for sid in story_ids]
    results = await asyncio.gather(*tasks)
    
    stories = []
    for story in results:
        if story and story.get("type") == "story":
            stories.append({
                "title": story.get("title", ""),
                "url": story.get("url", f"https://news.ycombinator.com/item?id={story.get('id')}"),
                "hn_url": f"https://news.ycombinator.com/item?id={story.get('id')}",
                "score": story.get("score", 0),
                "num_comments": story.get("descendants", 0),
                "author": story.get("by", ""),
                "time": story.get("time", 0),
                "source": "hackernews"
            })
    
    return stories


# =============================================================================
# LOBSTE.RS
# =============================================================================

@tool
async def fetch_lobsters(limit: int = 15) -> list[dict]:
    """
    Récupère les posts récents de Lobste.rs via leur API JSON.
    
    Args:
        limit: Nombre de posts à récupérer
    
    Returns:
        Liste de posts avec titre, url, score, tags
    """
    url = "https://lobste.rs/hottest.json"
    
    response = await safe_request(url)
    if not response:
        return []
    
    try:
        data = response.json()
        posts = []
        
        # Vérifier que data est bien une liste de dicts
        if not isinstance(data, list):
            logger.warning(f"Lobsters: format inattendu, type={type(data)}")
            return []
        
        for item in data[:limit]:
            # Ignorer si item n'est pas un dict
            if not isinstance(item, dict):
                continue
            posts.append({
                "title": item.get("title", ""),
                "url": item.get("url", "") or item.get("short_id_url", ""),
                "lobsters_url": item.get("short_id_url", ""),
                "score": item.get("score", 0),
                "num_comments": item.get("comment_count", 0),
                "tags": item.get("tags", []),
                "author": item.get("submitter_user", {}).get("username", "") if isinstance(item.get("submitter_user"), dict) else "",
                "created_at": item.get("created_at", ""),
                "source": "lobsters"
            })
        
        return posts
    except Exception as e:
        logger.error(f"Erreur parsing Lobsters: {e}")
        return []


# =============================================================================
# PRODUCT HUNT (via RSS/scraping basique)
# =============================================================================

@tool
async def fetch_producthunt(limit: int = 10) -> list[dict]:
    """
    Récupère les produits récents de Product Hunt.
    Note: Utilise le feed RSS public ou scraping basique.
    
    Args:
        limit: Nombre de produits à récupérer
    
    Returns:
        Liste de produits avec nom, tagline, url
    """
    # Utiliser la page d'accueil (scraping léger)
    url = "https://www.producthunt.com/"
    
    response = await safe_request(url)
    if not response:
        return []
    
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        products = []
        
        # Product Hunt utilise beaucoup de JS, le HTML statique est limité
        # On récupère ce qu'on peut depuis les balises meta et liens
        
        # Alternative: utiliser leur API GraphQL publique (limitée)
        # Pour l'instant, retourner une structure vide avec un message
        
        # Tentative de scraping des éléments visibles
        for item in soup.select("[data-test='post-item']")[:limit]:
            name_elem = item.select_one("[data-test='post-name']")
            tagline_elem = item.select_one("[data-test='post-tagline']")
            link_elem = item.select_one("a[href*='/posts/']")
            
            if name_elem:
                products.append({
                    "name": name_elem.get_text(strip=True),
                    "tagline": tagline_elem.get_text(strip=True) if tagline_elem else "",
                    "url": f"https://www.producthunt.com{link_elem.get('href', '')}" if link_elem else "",
                    "source": "producthunt"
                })
        
        # Si le scraping ne fonctionne pas bien, log et retourner vide
        if not products:
            logger.info("Product Hunt: scraping limité, essayer l'API")
        
        return products
    except Exception as e:
        logger.error(f"Erreur parsing Product Hunt: {e}")
        return []


# =============================================================================
# TECH NEWS (via RSS feeds)
# =============================================================================

@tool
async def fetch_tech_news_rss(
    limit_per_feed: int = 5
) -> list[dict]:
    """
    Récupère les articles tech via les flux RSS de sites majeurs.
    
    Args:
        limit_per_feed: Limite d'articles par feed
    
    Returns:
        Liste d'articles avec titre, url, source, date
    """
    import feedparser
    
    # Feeds par défaut (toujours utilisés)
    feeds = [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Wired", "https://www.wired.com/feed/rss"),
        ("ZDNet", "https://www.zdnet.com/news/rss.xml"),
    ]
    
    articles = []
    
    for source_name, feed_url in feeds:
        try:
            # feedparser est synchrone, on l'exécute dans un executor
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, feed_url)
            
            for entry in feed.entries[:limit_per_feed]:
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "source_name": source_name,
                    "summary": entry.get("summary", "")[:300],
                    "published": entry.get("published", ""),
                    "source": "tech_news"
                })
        except Exception as e:
            logger.warning(f"Erreur feed RSS {source_name}: {e}")
    
    return articles


# =============================================================================
# YOUTUBE (via recherche sans API key - limité)
# =============================================================================

@tool
async def fetch_youtube_search(
    query: str = "programming tutorial 2024",
    limit: int = 8
) -> list[dict]:
    """
    Recherche des vidéos YouTube récentes.
    Note: Sans API key, utilise le scraping basique (très limité).
    Préférer l'API YouTube Data v3 avec clé gratuite.
    
    Args:
        query: Termes de recherche
        limit: Nombre de résultats
    
    Returns:
        Liste de vidéos avec titre, url, channel
    """
    # NOTE: Le scraping YouTube est difficile sans API
    # Implémentation avec API key recommandée
    
    api_key = os.getenv("YOUTUBE_API_KEY")
    
    if api_key:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": limit,
            "order": "date",
            "publishedAfter": (datetime.now() - timedelta(days=7)).isoformat() + "Z",
            "key": api_key
        }
        
        response = await safe_request(url, params=params)
        if response:
            try:
                data = response.json()
                videos = []
                for item in data.get("items", []):
                    snippet = item.get("snippet", {})
                    video_id = item.get("id", {}).get("videoId", "")
                    videos.append({
                        "title": snippet.get("title", ""),
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "channel": snippet.get("channelTitle", ""),
                        "description": snippet.get("description", "")[:200],
                        "published_at": snippet.get("publishedAt", ""),
                        "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                        "source": "youtube"
                    })
                return videos
            except Exception as e:
                logger.error(f"Erreur parsing YouTube API: {e}")
    
    # Fallback sans API: retourner vide avec log
    logger.info("YouTube: API key non configurée, source ignorée")
    return []


# =============================================================================
# WEB SEARCH (via SerpAPI ou alternatives gratuites)
# =============================================================================

@tool
async def fetch_web_search(
    query: str,
    limit: int = 10
) -> list[dict]:
    """
    Recherche web générale via SerpAPI ou alternative gratuite.
    
    Args:
        query: Requête de recherche
        limit: Nombre de résultats
    
    Returns:
        Liste de résultats avec titre, url, snippet
    """
    # Option 1: SerpAPI (free tier: 100 requêtes/mois)
    serp_api_key = os.getenv("SERPAPI_KEY")
    
    if serp_api_key:
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": serp_api_key,
            "num": limit,
            "engine": "google"
        }
        
        response = await safe_request(url, params=params)
        if response:
            try:
                data = response.json()
                results = []
                for item in data.get("organic_results", [])[:limit]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "web_search"
                    })
                return results
            except Exception as e:
                logger.error(f"Erreur parsing SerpAPI: {e}")
    
    # Option 2: DuckDuckGo (gratuit, mais rate-limited)
    try:
        ddg_url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }
        
        response = await safe_request(ddg_url, params=params)
        if response:
            data = response.json()
            results = []
            
            # DDG retourne des résultats dans RelatedTopics
            for topic in data.get("RelatedTopics", [])[:limit]:
                if isinstance(topic, dict) and "FirstURL" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", ""),
                        "source": "web_search_ddg"
                    })
            
            return results
    except Exception as e:
        logger.error(f"Erreur DuckDuckGo: {e}")
    
    return []


# =============================================================================
# DEVHUNT / ALTERNATIVES
# =============================================================================

@tool
async def fetch_devhunt(limit: int = 10) -> list[dict]:
    """
    Récupère les outils dev récents de DevHunt.
    
    Args:
        limit: Nombre de résultats
    
    Returns:
        Liste d'outils avec nom, description, url
    """
    url = "https://devhunt.org/"
    
    response = await safe_request(url)
    if not response:
        return []
    
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        tools = []
        
        # DevHunt structure - à adapter selon leur HTML
        for item in soup.select(".tool-card, .product-card, article")[:limit]:
            title_elem = item.select_one("h2, h3, .title")
            desc_elem = item.select_one("p, .description")
            link_elem = item.select_one("a[href]")
            
            if title_elem:
                tools.append({
                    "name": title_elem.get_text(strip=True),
                    "description": desc_elem.get_text(strip=True)[:200] if desc_elem else "",
                    "url": link_elem.get("href", "") if link_elem else "",
                    "source": "devhunt"
                })
        
        return tools
    except Exception as e:
        logger.error(f"Erreur parsing DevHunt: {e}")
        return []


# =============================================================================
# ARXIV (pour les papers AI/ML)
# =============================================================================

@tool
async def fetch_arxiv_papers(
    category: str = "cs.AI",
    limit: int = 10
) -> list[dict]:
    """
    Récupère les papers récents d'arXiv dans une catégorie.
    
    Args:
        category: Catégorie arXiv (cs.AI, cs.LG, cs.CL, etc.)
        limit: Nombre de papers
    
    Returns:
        Liste de papers avec titre, auteurs, abstract, url
    """
    import feedparser
    
    url = f"http://export.arxiv.org/rss/{category}"
    
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, url)
        
        papers = []
        for entry in feed.entries[:limit]:
            # Nettoyer le titre (arXiv ajoute souvent des préfixes)
            title = entry.get("title", "").replace("\n", " ").strip()
            
            # Extraire les auteurs
            authors = entry.get("author", "")
            
            papers.append({
                "title": title,
                "url": entry.get("link", ""),
                "authors": authors,
                "summary": entry.get("summary", "")[:400],
                "published": entry.get("published", ""),
                "category": category,
                "source": "arxiv"
            })
        
        return papers
    except Exception as e:
        logger.error(f"Erreur arXiv {category}: {e}")
        return []


# =============================================================================
# REGISTRE DES TOOLS DISPONIBLES
# =============================================================================

AVAILABLE_TOOLS = {
    "reddit_programming": lambda: fetch_reddit_subreddit.ainvoke({
        "subreddit": "programming", "limit": 10
    }),
    "reddit_ml": lambda: fetch_reddit_subreddit.ainvoke({
        "subreddit": "MachineLearning", "limit": 10
    }),
    "reddit_llm": lambda: fetch_reddit_subreddit.ainvoke({
        "subreddit": "LocalLLaMA", "limit": 10
    }),
    "reddit_devops": lambda: fetch_reddit_subreddit.ainvoke({
        "subreddit": "devops", "limit": 10
    }),
    "reddit_selfhosted": lambda: fetch_reddit_subreddit.ainvoke({
        "subreddit": "selfhosted", "limit": 10
    }),
    "reddit_netsec": lambda: fetch_reddit_subreddit.ainvoke({
        "subreddit": "netsec", "limit": 10
    }),
    "reddit_webdev": lambda: fetch_reddit_subreddit.ainvoke({
        "subreddit": "webdev", "limit": 10
    }),
    "github_trending": lambda: fetch_github_trending.ainvoke({
        "language": "", "since": "weekly"
    }),
    "hackernews": lambda: fetch_hackernews.ainvoke({
        "story_type": "top", "limit": 15
    }),
    "lobsters": lambda: fetch_lobsters.ainvoke({"limit": 15}),
    "producthunt": lambda: fetch_producthunt.ainvoke({"limit": 10}),
    "devhunt": lambda: fetch_devhunt.ainvoke({"limit": 10}),
    "tech_news": lambda: fetch_tech_news_rss.ainvoke({
        "limit_per_feed": 5
    }),
    "youtube_tech": lambda: fetch_youtube_search.ainvoke({
        "query": "programming devops AI tutorial 2024", "limit": 8
    }),
    "web_search": lambda: fetch_web_search.ainvoke({
        "query": "latest tech news developer tools 2024", "limit": 10
    }),
    "arxiv_ai": lambda: fetch_arxiv_papers.ainvoke({
        "category": "cs.AI", "limit": 10
    }),
}

# Liste des tools pour LangChain
ALL_TOOLS = [
    fetch_reddit_subreddit,
    fetch_reddit_multiple,
    fetch_github_trending,
    fetch_hackernews,
    fetch_lobsters,
    fetch_producthunt,
    fetch_tech_news_rss,
    fetch_youtube_search,
    fetch_web_search,
    fetch_devhunt,
    fetch_arxiv_papers,
]
