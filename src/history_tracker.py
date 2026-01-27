"""
Module de gestion de l'historique des items envoyés.
Permet d'éviter les doublons dans les emails tout en les gardant dans le README.
"""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple


HISTORY_FILE = Path("output/sent_history.json")
HISTORY_RETENTION_DAYS = 14  # Garder l'historique 14 jours


def get_item_hash(item: Dict) -> str:
    """Génère un hash unique pour un item basé sur son URL ou titre."""
    # Priorité: URL > titre
    key = item.get("url") or item.get("link") or item.get("title", "")
    return hashlib.md5(key.lower().encode()).hexdigest()[:16]


def load_history() -> Dict:
    """Charge l'historique des items envoyés."""
    if not HISTORY_FILE.exists():
        return {"items": {}, "last_cleanup": datetime.now().isoformat()}
    
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"items": {}, "last_cleanup": datetime.now().isoformat()}


def save_history(history: Dict) -> None:
    """Sauvegarde l'historique."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def cleanup_old_entries(history: Dict) -> Dict:
    """Supprime les entrées plus vieilles que HISTORY_RETENTION_DAYS."""
    cutoff = datetime.now() - timedelta(days=HISTORY_RETENTION_DAYS)
    cutoff_str = cutoff.isoformat()
    
    history["items"] = {
        h: data for h, data in history["items"].items()
        if data.get("first_seen", "") > cutoff_str
    }
    history["last_cleanup"] = datetime.now().isoformat()
    return history


def separate_new_and_seen(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Sépare les items en nouveaux et déjà vus.
    
    Returns:
        (nouveaux_items, items_deja_vus)
    """
    history = load_history()
    
    # Cleanup périodique
    last_cleanup = datetime.fromisoformat(history.get("last_cleanup", "2000-01-01"))
    if datetime.now() - last_cleanup > timedelta(days=1):
        history = cleanup_old_entries(history)
    
    new_items = []
    seen_items = []
    seen_hashes = history.get("items", {})
    
    for item in items:
        item_hash = get_item_hash(item)
        
        if item_hash in seen_hashes:
            # Déjà vu - mettre à jour le compteur
            seen_hashes[item_hash]["times_seen"] = seen_hashes[item_hash].get("times_seen", 1) + 1
            seen_hashes[item_hash]["last_seen"] = datetime.now().isoformat()
            item["_times_seen"] = seen_hashes[item_hash]["times_seen"]
            seen_items.append(item)
        else:
            # Nouveau !
            new_items.append(item)
    
    return new_items, seen_items


def mark_items_as_sent(items: List[Dict]) -> None:
    """Marque les items comme envoyés dans l'historique."""
    history = load_history()
    
    now = datetime.now().isoformat()
    
    for item in items:
        item_hash = get_item_hash(item)
        if item_hash not in history["items"]:
            history["items"][item_hash] = {
                "title": item.get("title", "")[:100],
                "url": item.get("url") or item.get("link", ""),
                "first_seen": now,
                "last_seen": now,
                "times_seen": 1
            }
    
    save_history(history)


def get_history_stats() -> Dict:
    """Retourne des statistiques sur l'historique."""
    history = load_history()
    items = history.get("items", {})
    
    return {
        "total_items": len(items),
        "last_cleanup": history.get("last_cleanup"),
        "retention_days": HISTORY_RETENTION_DAYS
    }
