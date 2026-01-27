#!/usr/bin/env python3
"""
Point d'entrée principal de l'agent de veille technologique.

Modes d'exécution:
- CLI: python main.py "Quoi de neuf en IA ?"
- HTTP: python main.py --serve
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Imports locaux
from config import get_config, Config
from agent.state import create_initial_state
from agent.graph import create_tech_watch_graph


async def run_tech_watch(
    query: str = "Quoi de neuf en tech ?",
    focus: str = "general",
    period: str = "week",
    max_items: int = 10
) -> str:
    """
    Exécute une veille technologique.
    
    Args:
        query: Requête utilisateur
        focus: Focus thématique (general, ai, devops, web, security, tools, all)
        period: Période (today, week, month)
        max_items: Limite d'items par source
        
    Returns:
        Synthèse de la veille en Markdown
    """
    config = get_config()
    
    # Validation
    warnings = config.validate()
    for w in warnings:
        logger.warning(w)
    
    if not config.llm.has_llm:
        return "❌ Erreur: Aucun LLM configuré. Définir GOOGLE_API_KEY ou MISTRAL_API_KEY."
    
    # Créer le state initial
    initial_state = create_initial_state(
        user_query=query,
        focus=focus,
        period=period,
        max_items_per_source=max_items
    )
    
    # Créer et exécuter le graph
    logger.info(f"🚀 Démarrage de la veille: '{query}' (focus: {focus})")
    
    graph = create_tech_watch_graph()
    
    try:
        final_state = await graph.ainvoke(initial_state)
        synthesis = final_state.get("synthesis", "Aucun résultat")
        
        logger.info("✅ Veille terminée")
        return synthesis
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'exécution: {e}")
        return f"❌ Erreur: {str(e)}"


def run_cli():
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(
        description="Agent de veille technologique",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python main.py "Quoi de neuf en IA ?"
  python main.py --focus devops "Nouveautés Kubernetes"
  python main.py --serve --port 8080
        """
    )
    
    parser.add_argument(
        "query",
        nargs="?",
        default="Quoi de neuf en tech ?",
        help="Requête de veille (défaut: 'Quoi de neuf en tech ?')"
    )
    
    parser.add_argument(
        "--focus",
        choices=["general", "ai", "devops", "web", "security", "tools", "all"],
        default="general",
        help="Focus thématique (défaut: general)"
    )
    
    parser.add_argument(
        "--period",
        choices=["today", "week", "month"],
        default="week",
        help="Période de recherche (défaut: week)"
    )
    
    parser.add_argument(
        "--max-items",
        type=int,
        default=10,
        help="Limite d'items par source (défaut: 10)"
    )
    
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Démarrer en mode serveur HTTP"
    )
    
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host du serveur HTTP (défaut: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port du serveur HTTP (défaut: 8080)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Mode debug (logs détaillés)"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Afficher le statut de la configuration"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Sauvegarder le résultat dans un fichier (auto: génère veille_YYYY-MM-DD.md)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Dossier de sortie pour les fichiers (défaut: output)"
    )
    
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Envoyer le résultat par email (ex: --email dorianppl852@gmail.com)"
    )
    
    args = parser.parse_args()
    
    # Mode debug
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Afficher le statut
    if args.status:
        config = get_config()
        config.print_status()
        return
    
    # Mode serveur HTTP
    if args.serve:
        run_http_server(args.host, args.port)
        return
    
    # Mode CLI standard
    result = asyncio.run(run_tech_watch(
        query=args.query,
        focus=args.focus,
        period=args.period,
        max_items=args.max_items
    ))
    
    # Sauvegarder dans un fichier si demandé
    if args.output is not None:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Générer le nom de fichier avec la date
        if args.output == "" or args.output.lower() == "auto":
            filename = f"veille_{datetime.now().strftime('%Y-%m-%d')}.md"
        else:
            filename = args.output
            if not filename.endswith(".md"):
                filename += ".md"
        
        output_path = output_dir / filename
        
        # Écrire le fichier
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# 🔍 Veille Tech - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
            f.write(f"**Requête:** {args.query}\n")
            f.write(f"**Focus:** {args.focus}\n\n")
            f.write("---\n\n")
            f.write(result)
        
        logger.info(f"📄 Résultat sauvegardé dans: {output_path}")
        print(f"\n📄 Fichier créé: {output_path}")
    
    # Envoyer par email si demandé
    if args.email:
        try:
            from email_sender import send_veille_email
            send_veille_email(result, to_email=args.email)
        except Exception as e:
            logger.error(f"❌ Erreur envoi email: {e}")
    
    print("\n" + "=" * 60)
    print(result)
    print("=" * 60)


def run_http_server(host: str = "0.0.0.0", port: int = 8080):
    """Démarre un serveur HTTP simple."""
    
    try:
        from aiohttp import web
    except ImportError:
        logger.error("aiohttp requis pour le mode serveur: pip install aiohttp")
        sys.exit(1)
    
    async def health_handler(request):
        """Endpoint de health check."""
        return web.json_response({
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        })
    
    async def watch_handler(request):
        """Endpoint principal de veille."""
        try:
            # Paramètres depuis query string ou body JSON
            if request.method == "POST":
                data = await request.json()
            else:
                data = dict(request.query)
            
            query = data.get("query", "Quoi de neuf en tech ?")
            focus = data.get("focus", "general")
            period = data.get("period", "week")
            max_items = int(data.get("max_items", 10))
            
            logger.info(f"📨 Requête reçue: {query}")
            
            result = await run_tech_watch(
                query=query,
                focus=focus,
                period=period,
                max_items=max_items
            )
            
            return web.json_response({
                "success": True,
                "query": query,
                "focus": focus,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Erreur HTTP: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)
    
    async def index_handler(request):
        """Page d'accueil simple."""
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Tech Watch Agent</title>
    <style>
        body { font-family: system-ui; max-width: 800px; margin: 50px auto; padding: 20px; }
        h1 { color: #333; }
        .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
        code { background: #e0e0e0; padding: 2px 6px; border-radius: 3px; }
    </style>
</head>
<body>
    <h1>🔍 Tech Watch Agent</h1>
    <p>Agent de veille technologique propulsé par LangGraph + LangChain</p>
    
    <h2>Endpoints</h2>
    
    <div class="endpoint">
        <h3>GET /health</h3>
        <p>Health check</p>
    </div>
    
    <div class="endpoint">
        <h3>GET /watch</h3>
        <p>Lancer une veille</p>
        <p>Paramètres:</p>
        <ul>
            <li><code>query</code> - Requête (défaut: "Quoi de neuf en tech ?")</li>
            <li><code>focus</code> - Focus: general, ai, devops, web, security, tools, all</li>
            <li><code>period</code> - Période: today, week, month</li>
            <li><code>max_items</code> - Limite par source (défaut: 10)</li>
        </ul>
        <p>Exemple: <code>/watch?focus=ai&period=week</code></p>
    </div>
    
    <div class="endpoint">
        <h3>POST /watch</h3>
        <p>Lancer une veille (JSON body)</p>
        <pre>{"query": "Nouveautés Kubernetes", "focus": "devops"}</pre>
    </div>
</body>
</html>
        """
        return web.Response(text=html, content_type="text/html")
    
    # Créer l'app
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/watch", watch_handler)
    app.router.add_post("/watch", watch_handler)
    
    logger.info(f"🌐 Démarrage du serveur HTTP sur http://{host}:{port}")
    
    # Afficher le statut de la config
    config = get_config()
    config.print_status()
    
    web.run_app(app, host=host, port=port, print=None)


if __name__ == "__main__":
    run_cli()
