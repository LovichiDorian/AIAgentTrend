"""
Construction du StateGraph LangGraph pour l'agent de veille.
"""

from langgraph.graph import StateGraph, END
from .state import TechWatchState
from .nodes import (
    planning_node,
    collection_node,
    filtering_node,
    synthesis_node,
    output_node
)


def create_tech_watch_graph() -> StateGraph:
    """
    Crée et compile le StateGraph de l'agent de veille.
    
    Architecture du graph:
    
        [START]
           │
           ▼
      ┌─────────┐
      │ Planning │  ← Décide quelles sources interroger
      └────┬────┘
           │
           ▼
      ┌──────────┐
      │Collection│  ← Appelle les tools en parallèle
      └────┬─────┘
           │
           ▼
      ┌──────────┐
      │ Filtering│  ← Déduplique et priorise
      └────┬─────┘
           │
           ▼
      ┌──────────┐
      │Synthesis │  ← Génère la synthèse via LLM
      └────┬─────┘
           │
           ▼
      ┌────────┐
      │ Output │   ← Formate la sortie finale
      └────┬───┘
           │
           ▼
         [END]
    
    Returns:
        StateGraph compilé prêt à être exécuté
    """
    
    # Créer le graph avec le type de state
    workflow = StateGraph(TechWatchState)
    
    # Ajouter les nœuds
    workflow.add_node("planning", planning_node)
    workflow.add_node("collection", collection_node)
    workflow.add_node("filtering", filtering_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("output", output_node)
    
    # Définir les arêtes (flow linéaire pour cette v1)
    workflow.set_entry_point("planning")
    
    workflow.add_edge("planning", "collection")
    workflow.add_edge("collection", "filtering")
    workflow.add_edge("filtering", "synthesis")
    workflow.add_edge("synthesis", "output")
    workflow.add_edge("output", END)
    
    # Compiler le graph
    app = workflow.compile()
    
    return app


def create_tech_watch_graph_with_routing() -> StateGraph:
    """
    Version avancée du graph avec routage conditionnel.
    
    Permet de:
    - Sauter certaines sources si budget dépassé
    - Réessayer une collecte si échec
    - Générer un fallback si LLM indisponible
    
    Returns:
        StateGraph avec routage conditionnel
    """
    
    workflow = StateGraph(TechWatchState)
    
    # Nœuds
    workflow.add_node("planning", planning_node)
    workflow.add_node("collection", collection_node)
    workflow.add_node("filtering", filtering_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("output", output_node)
    
    # Fonction de routage après collection
    def should_continue_collection(state: TechWatchState) -> str:
        """Décide si on continue ou si on a assez de données."""
        source_results = state.get("source_results", {})
        errors = state.get("errors", [])
        
        # Compter les items collectés
        total_items = sum(
            len(r.items) if hasattr(r, 'items') else len(r.get('items', []))
            for r in source_results.values()
        )
        
        # Si on a au moins quelques items, continuer
        if total_items >= 5:
            return "filtering"
        
        # Si toutes les sources ont échoué, aller directement à output avec erreur
        if len(errors) == len(state.get("sources_to_query", [])):
            return "output"
        
        return "filtering"
    
    # Fonction de routage après synthèse
    def check_synthesis_success(state: TechWatchState) -> str:
        """Vérifie si la synthèse a réussi."""
        synthesis = state.get("synthesis", "")
        
        if synthesis and len(synthesis) > 100:
            return "output"
        
        # Synthèse trop courte ou vide, aller quand même à output
        return "output"
    
    # Définir le flow
    workflow.set_entry_point("planning")
    workflow.add_edge("planning", "collection")
    
    # Routage conditionnel après collection
    workflow.add_conditional_edges(
        "collection",
        should_continue_collection,
        {
            "filtering": "filtering",
            "output": "output"
        }
    )
    
    workflow.add_edge("filtering", "synthesis")
    
    # Routage conditionnel après synthèse
    workflow.add_conditional_edges(
        "synthesis",
        check_synthesis_success,
        {
            "output": "output"
        }
    )
    
    workflow.add_edge("output", END)
    
    return workflow.compile()


# Export du graph par défaut
def get_default_graph():
    """Retourne le graph par défaut (version simple)."""
    return create_tech_watch_graph()
