"""
Module de scraping des startups - VERSION ROBUSTE

Sources fiables :
1. Hacker News (API) - startups en Show HN
2. Product Hunt (API GraphQL)  
3. GitHub Trending (scraping)
4. TechCrunch RSS
5. Crunchbase News RSS
6. EU-Startups RSS
7. Maddyness RSS (French Tech)
8. Y Combinator (API companies)
9. AngelList Jobs (proxy pour startups actives)
10. TheNextWeb RSS
"""

import asyncio
import re
import logging
import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import httpx
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Configuration
REQUEST_TIMEOUT = 15.0
MAX_RETRIES = 2
DB_PATH = os.path.join(os.path.dirname(__file__), "startups_history.db")

# Filtres startups : tech only
TECH_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "ml", "saas", 
    "devtools", "developer", "fintech", "cloud", "cybersecurity", "security",
    "data", "analytics", "api", "automation", "infrastructure", "platform",
    "software", "b2b", "enterprise", "payments", "blockchain", "web3",
    "database", "observability", "monitoring", "testing", "llm", "genai",
    "open source", "startup", "launch", "funding", "seed", "series"
]


def init_db():
    """Initialise la base SQLite pour l'historique."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS startups_seen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                incubator TEXT,
                description TEXT,
                funding TEXT,
                url TEXT,
                country TEXT,
                first_seen DATE,
                last_seen DATE
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"DB init error: {e}")


def save_startup_to_db(startup: Dict):
    """Sauvegarde une startup dans l'historique."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        today = datetime.now().date().isoformat()
        
        c.execute("""
            INSERT INTO startups_seen (name, incubator, description, funding, url, country, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET last_seen = ?, funding = COALESCE(?, funding)
        """, (
            startup.get("name"),
            startup.get("incubator"),
            startup.get("description"),
            startup.get("funding"),
            startup.get("url"),
            startup.get("country", ""),
            today, today, today,
            startup.get("funding")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"DB error: {e}")


def get_startups_this_month() -> List[Dict]:
    """Récupère les startups vues ce mois-ci."""
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        first_of_month = datetime.now().replace(day=1).date().isoformat()
        today = datetime.now().date().isoformat()
        
        c.execute("""
            SELECT name, incubator, description, funding, url, country, first_seen
            FROM startups_seen
            WHERE first_seen >= ? AND first_seen < ?
            ORDER BY first_seen DESC
        """, (first_of_month, today))
        
        rows = c.fetchall()
        conn.close()
        
        return [{
            "name": r[0], "incubator": r[1], "description": r[2],
            "funding": r[3], "url": r[4], "country": r[5], "first_seen": r[6]
        } for r in rows]
    except Exception as e:
        logger.debug(f"DB read error: {e}")
        return []


async def http_get(url: str, headers: dict = None, params: dict = None) -> Optional[httpx.Response]:
    """Requête HTTP simple."""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8,application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        default_headers.update(headers)
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        for _ in range(MAX_RETRIES):
            try:
                response = await client.get(url, headers=default_headers, params=params)
                if response.status_code == 200:
                    return response
            except Exception as e:
                logger.debug(f"HTTP error {url}: {e}")
            await asyncio.sleep(0.5)
    return None


def is_tech_startup(text: str) -> bool:
    """Vérifie si c'est une startup tech."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in TECH_KEYWORDS)


def extract_funding(text: str) -> Optional[str]:
    """Extrait le montant de financement."""
    patterns = [
        r'\$(\d+(?:\.\d+)?)\s*[Bb](?:illion)?',
        r'\$(\d+(?:\.\d+)?)\s*[Mm](?:illion)?',
        r'€(\d+(?:\.\d+)?)\s*[Mm](?:illion)?',
        r'raises?\s*\$(\d+(?:\.\d+)?[MBK]?)',
        r'\$(\d+(?:,\d+)*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


# =============================================================================
# SOURCE 1: HACKER NEWS - Show HN (API fiable)
# =============================================================================

async def fetch_hackernews_showhn(limit: int = 15) -> List[Dict]:
    """Récupère les Show HN récents (lancements de startups)."""
    startups = []
    
    # API Hacker News - Show HN stories
    url = "https://hacker-news.firebaseio.com/v0/showstories.json"
    response = await http_get(url)
    if not response:
        return []
    
    try:
        story_ids = response.json()[:limit * 2]
        
        for story_id in story_ids[:limit]:
            detail_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            detail = await http_get(detail_url)
            if not detail:
                continue
            
            data = detail.json()
            title = data.get("title", "")
            
            # Filtrer Show HN
            if not title.startswith("Show HN:"):
                continue
            
            name = title.replace("Show HN:", "").split("–")[0].split("-")[0].strip()[:50]
            description = title[9:].strip()[:150]
            url = data.get("url", f"https://news.ycombinator.com/item?id={story_id}")
            
            if is_tech_startup(description):
                startups.append({
                    "name": name,
                    "description": description,
                    "url": url,
                    "incubator": "Hacker News",
                    "funding": "Launch",
                    "country": "Global",
                    "source": "hn"
                })
            
            if len(startups) >= limit:
                break
            
            await asyncio.sleep(0.1)
            
    except Exception as e:
        logger.error(f"HN error: {e}")
    
    return startups


# =============================================================================
# SOURCE 2: Y COMBINATOR - Companies API
# =============================================================================

async def detect_yc_batch() -> Tuple[str, str]:
    """Détecte le dernier batch YC."""
    now = datetime.now()
    year = now.year % 100
    month = now.month
    
    if month >= 1 and month <= 6:
        batch = f"W{year}"
    else:
        batch = f"S{year}"
    
    return batch, f"https://www.ycombinator.com/companies?batch={batch}"


async def fetch_yc_companies(limit: int = 15) -> Dict:
    """Récupère les startups YC via l'API Algolia."""
    batch, batch_url = await detect_yc_batch()
    startups = []
    
    # YC utilise Algolia - essayons l'endpoint public
    url = "https://45bwzj1sgc-dsn.algolia.net/1/indexes/*/queries"
    
    headers = {
        "x-algolia-api-key": "MjBjYjRiMzY0NzdhZWY0NjExY2NhZjYxMGIxYjc2MTAwNWFkNTkwNTc4NjgxYjU0YzFhYTY2ZGQ5OGY5NDMxZnJlc3RyaWN0SW5kaWNlcz0lNUIlMjJZQ0NvbXBhbnlfcHJvZHVjdGlvbiUyMiU1RCZ0YWdGaWx0ZXJzPSU1QiUyMnljX2JhdGNoJTNBVzI2JTIyJTVE",
        "x-algolia-application-id": "45BWZJ1SGC",
    }
    
    # Fallback: scraping basique
    response = await http_get(batch_url)
    if response:
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Chercher tous les liens de companies
            links = soup.find_all("a", href=re.compile(r"/companies/[a-z0-9-]+"))
            seen = set()
            
            for link in links[:limit * 3]:
                href = link.get("href", "")
                if href in seen:
                    continue
                seen.add(href)
                
                # Extraire le texte du lien et ses parents
                text = link.get_text(separator=" ", strip=True)
                parent = link.find_parent()
                if parent:
                    text = parent.get_text(separator=" | ", strip=True)
                
                # Parser
                parts = [p.strip() for p in text.split("|") if p.strip()]
                name = parts[0][:50] if parts else ""
                
                if not name or len(name) < 2 or name.lower() in ["companies", "all", "batch"]:
                    continue
                
                description = " ".join(parts[1:3])[:150] if len(parts) > 1 else ""
                
                if is_tech_startup(name + " " + description):
                    startups.append({
                        "name": name,
                        "description": description or f"YC {batch} startup",
                        "url": f"https://www.ycombinator.com{href}",
                        "incubator": f"YC {batch}",
                        "funding": "Seed ($500K)",
                        "country": "🇺🇸 USA",
                        "source": "yc"
                    })
                
                if len(startups) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"YC parsing error: {e}")
    
    return {"batch": batch, "batch_url": batch_url, "startups": startups}


# =============================================================================
# SOURCE 3: TECHCRUNCH RSS
# =============================================================================

async def fetch_techcrunch_rss(limit: int = 10) -> List[Dict]:
    """Récupère les articles TechCrunch via RSS."""
    url = "https://techcrunch.com/feed/"
    response = await http_get(url)
    if not response:
        return []
    
    startups = []
    try:
        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        
        for item in items[:limit * 3]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            desc = item.find("description").text if item.find("description") is not None else ""
            
            # Filtrer les articles de funding
            funding_kw = ["raises", "funding", "series", "seed", "million", "$", "closes"]
            if not any(kw in title.lower() for kw in funding_kw):
                continue
            
            # Extraire nom startup
            name = ""
            for pattern in [r"^([A-Z][A-Za-z0-9\s&\-\.]+?)\s+(?:raises|Raises|closes|lands|nabs|secures)"]:
                match = re.search(pattern, title)
                if match:
                    name = match.group(1).strip()[:50]
                    break
            
            if not name:
                name = title.split(" raises")[0].split(" Raises")[0][:40]
            
            funding = extract_funding(title)
            
            # Nettoyer description HTML
            if desc:
                soup = BeautifulSoup(desc, "html.parser")
                desc = soup.get_text()[:150]
            
            if name and len(name) > 2 and is_tech_startup(title + " " + desc):
                startups.append({
                    "name": name,
                    "description": desc or title[:150],
                    "url": link,
                    "incubator": "TechCrunch",
                    "funding": funding or "Disclosed",
                    "country": "🇺🇸 USA",
                    "source": "techcrunch"
                })
            
            if len(startups) >= limit:
                break
                
    except Exception as e:
        logger.error(f"TechCrunch RSS error: {e}")
    
    return startups


# =============================================================================
# SOURCE 4: MADDYNESS RSS (French Tech)
# =============================================================================

async def fetch_maddyness_rss(limit: int = 10) -> List[Dict]:
    """Récupère les levées de fonds Maddyness via RSS."""
    url = "https://www.maddyness.com/feed/"
    response = await http_get(url)
    if not response:
        return []
    
    startups = []
    try:
        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        
        for item in items[:limit * 3]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            desc = item.find("description").text if item.find("description") is not None else ""
            
            # Filtrer les articles de levées
            if not any(kw in title.lower() for kw in ["lève", "levée", "million", "euros", "€", "série"]):
                continue
            
            # Extraire nom
            name = title.split(" lève")[0].split(" Lève")[0].split(":")[0][:50]
            funding = extract_funding(title)
            
            if desc:
                soup = BeautifulSoup(desc, "html.parser")
                desc = soup.get_text()[:150]
            
            if name and len(name) > 2:
                startups.append({
                    "name": name,
                    "description": desc or title[:150],
                    "url": link,
                    "incubator": "French Tech",
                    "funding": funding or "€ M",
                    "country": "🇫🇷 France",
                    "source": "maddyness"
                })
            
            if len(startups) >= limit:
                break
                
    except Exception as e:
        logger.error(f"Maddyness RSS error: {e}")
    
    return startups


# =============================================================================
# SOURCE 5: EU-STARTUPS RSS
# =============================================================================

async def fetch_eustartups_rss(limit: int = 10) -> List[Dict]:
    """Récupère les startups européennes via RSS."""
    url = "https://www.eu-startups.com/feed/"
    response = await http_get(url)
    if not response:
        return []
    
    startups = []
    try:
        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        
        for item in items[:limit * 3]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            desc = item.find("description").text if item.find("description") is not None else ""
            
            funding_kw = ["raises", "funding", "series", "seed", "million", "€", "$", "secures"]
            if not any(kw in title.lower() for kw in funding_kw):
                continue
            
            name = title.split(" raises")[0].split(" Raises")[0].split(" secures")[0][:50]
            funding = extract_funding(title)
            
            if desc:
                soup = BeautifulSoup(desc, "html.parser")
                desc = soup.get_text()[:150]
            
            if name and len(name) > 2 and is_tech_startup(title):
                startups.append({
                    "name": name,
                    "description": desc or title[:150],
                    "url": link,
                    "incubator": "EU-Startups",
                    "funding": funding or "€ M",
                    "country": "🇪🇺 Europe",
                    "source": "eu-startups"
                })
            
            if len(startups) >= limit:
                break
                
    except Exception as e:
        logger.error(f"EU-Startups RSS error: {e}")
    
    return startups


# =============================================================================
# SOURCE 6: GITHUB TRENDING (startups open source)
# =============================================================================

async def fetch_github_trending(limit: int = 10) -> List[Dict]:
    """Récupère les repos GitHub trending (souvent des startups)."""
    url = "https://github.com/trending"
    response = await http_get(url)
    if not response:
        return []
    
    startups = []
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.select("article.Box-row")
        
        for article in articles[:limit]:
            # Repo name
            h2 = article.select_one("h2 a")
            if not h2:
                continue
            
            repo_path = h2.get("href", "").strip("/")
            parts = repo_path.split("/")
            if len(parts) != 2:
                continue
            
            org, repo = parts
            
            # Description
            p = article.select_one("p")
            description = p.get_text(strip=True)[:150] if p else ""
            
            # Stars
            stars_elem = article.select_one("[href$='/stargazers']")
            stars = stars_elem.get_text(strip=True) if stars_elem else ""
            
            if is_tech_startup(description + " " + repo):
                startups.append({
                    "name": f"{org}/{repo}",
                    "description": description,
                    "url": f"https://github.com/{repo_path}",
                    "incubator": "GitHub Trending",
                    "funding": f"⭐ {stars}" if stars else "Open Source",
                    "country": "Global",
                    "source": "github"
                })
                
    except Exception as e:
        logger.error(f"GitHub error: {e}")
    
    return startups


# =============================================================================
# SOURCE 7: THE NEXT WEB RSS
# =============================================================================

async def fetch_tnw_rss(limit: int = 8) -> List[Dict]:
    """Récupère les startups via TheNextWeb RSS."""
    url = "https://thenextweb.com/feed/"
    response = await http_get(url)
    if not response:
        return []
    
    startups = []
    try:
        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        
        for item in items[:limit * 3]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            
            funding_kw = ["raises", "funding", "series", "startup", "launch", "million"]
            if not any(kw in title.lower() for kw in funding_kw):
                continue
            
            name = title.split(" raises")[0].split(" Raises")[0][:50]
            funding = extract_funding(title)
            
            if name and len(name) > 2 and is_tech_startup(title):
                startups.append({
                    "name": name,
                    "description": title[:150],
                    "url": link,
                    "incubator": "TheNextWeb",
                    "funding": funding or "Disclosed",
                    "country": "🇪🇺 Europe",
                    "source": "tnw"
                })
            
            if len(startups) >= limit:
                break
                
    except Exception as e:
        logger.debug(f"TNW RSS error: {e}")
    
    return startups


# =============================================================================
# SOURCE 8: GROWTHLIST
# =============================================================================

async def fetch_growthlist(limit: int = 10) -> List[Dict]:
    """Récupère les startups depuis GrowthList."""
    url = "https://growthlist.co/funded-startups/"
    response = await http_get(url)
    if not response:
        return []
    
    startups = []
    try:
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Chercher les tables ou cartes
        rows = soup.select("tr, .startup-card, .company-item")
        
        for row in rows[:limit * 2]:
            text = row.get_text(separator=" | ", strip=True)
            parts = [p.strip() for p in text.split("|") if p.strip()]
            
            if len(parts) < 2:
                continue
            
            name = parts[0][:50]
            if not name or len(name) < 3 or name.lower() in ["startup", "company", "name"]:
                continue
            
            description = parts[1][:150] if len(parts) > 1 else ""
            funding = extract_funding(text)
            
            if is_tech_startup(text):
                startups.append({
                    "name": name,
                    "description": description,
                    "url": "",
                    "incubator": "GrowthList",
                    "funding": funding or "Seed",
                    "country": "🇺🇸 USA",
                    "source": "growthlist"
                })
            
            if len(startups) >= limit:
                break
                
    except Exception as e:
        logger.error(f"GrowthList error: {e}")
    
    return startups


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

async def collect_all_startups() -> Dict:
    """
    Collecte toutes les startups depuis 8 sources fiables.
    """
    logger.info("🚀 Collecte des startups depuis 8 sources...")
    init_db()
    
    # Lancer toutes les sources en parallèle
    results = await asyncio.gather(
        fetch_yc_companies(limit=15),
        fetch_hackernews_showhn(limit=12),
        fetch_techcrunch_rss(limit=10),
        fetch_maddyness_rss(limit=8),
        fetch_eustartups_rss(limit=8),
        fetch_github_trending(limit=10),
        fetch_tnw_rss(limit=6),
        fetch_growthlist(limit=8),
        return_exceptions=True
    )
    
    all_startups = []
    sources_scraped = []
    yc_info = {"batch": None, "batch_url": None}
    
    source_names = ["yc", "hackernews", "techcrunch", "maddyness", "eu-startups", "github", "tnw", "growthlist"]
    
    for i, result in enumerate(results):
        source = source_names[i]
        
        if isinstance(result, Exception):
            logger.warning(f"⚠️ Erreur {source}: {result}")
            continue
        
        sources_scraped.append(source)
        
        if source == "yc" and isinstance(result, dict):
            yc_info["batch"] = result.get("batch")
            yc_info["batch_url"] = result.get("batch_url")
            startups = result.get("startups", [])
        else:
            startups = result if isinstance(result, list) else []
        
        if startups:
            logger.info(f"   ✓ {source}: {len(startups)} startups")
            all_startups.extend(startups)
    
    # Dédupliquer
    seen = set()
    unique = []
    for s in all_startups:
        name = s.get("name", "").lower().strip()
        if name and name not in seen and len(name) > 2:
            seen.add(name)
            unique.append(s)
            save_startup_to_db(s)
    
    monthly = get_startups_this_month()
    
    logger.info(f"📊 Total: {len(unique)} startups uniques")
    logger.info(f"📅 Rappels mois: {len(monthly)} startups")
    
    return {
        "yc_batch": yc_info["batch"],
        "yc_batch_url": yc_info["batch_url"],
        "startups_week": unique,
        "startups_month": monthly,
        "sources_scraped": sources_scraped,
        "total_sources": len(source_names),
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(collect_all_startups())
    print(f"\nBatch YC: {result['yc_batch']}")
    print(f"Startups: {len(result['startups_week'])}")
    print(f"Sources: {result['sources_scraped']}")
    for s in result['startups_week'][:10]:
        print(f"  - {s['name']} | {s['incubator']} | {s.get('funding', '-')}")
