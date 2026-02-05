"""Pipeline-based entry point for local LLMs.

This version uses a simple intent parser + deterministic pipeline,
which works much better with smaller local models like Qwen 7B.

Usage:
    python main_local.py                    # Interactive mode
    python main_local.py "Riga to Vilnius"  # Single query mode
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from src.pipeline import RoutePlanningPipeline, parse_route_intent
from src.pipeline.intent_parser import parse_route_intent_simple, RouteIntent


console = Console()


async def plan_route(user_input: str) -> str:
    """
    Plan a route from natural language input.
    
    Uses LLM for intent parsing, then deterministic pipeline for execution.
    Falls back to regex parsing if LLM fails.
    """
    console.print("\n[dim]Parsing your request...[/dim]")
    
    # Try LLM-based intent parsing first
    intent = await parse_route_intent(user_input)
    
    # Fallback to regex-based parsing
    if not intent or not intent.start_location or not intent.end_location:
        intent = parse_route_intent_simple(user_input)
    
    if not intent or not intent.start_location or not intent.end_location:
        return "❌ I couldn't understand your route request. Please try something like:\n" \
               "  • 'Plan a route from Riga to Vilnius'\n" \
               "  • 'Tallinn to Tartu, 100km per day'\n" \
               "  • 'From Kaunas to Palanga with MTB'"
    
    console.print(f"[green]✓[/green] Route: {intent.start_location} → {intent.end_location}")
    console.print(f"[green]✓[/green] Daily distance: {intent.daily_distance_km:.0f} km")
    console.print(f"[green]✓[/green] Profile: {intent.profile}\n")
    
    # Execute the pipeline
    pipeline = RoutePlanningPipeline(show_progress=True)
    result = await pipeline.execute(intent)
    
    return result.format_summary()


async def interactive_mode():
    """Run interactive chat mode."""
    
    console.print("\n[bold blue]🚴 Bike Packing Route Planner (Local Mode)[/bold blue]\n")
    
    console.print(Panel(
        "I'm your bike packing route planning assistant!\n\n"
        "[bold]How to use:[/bold]\n"
        "  • 'Plan a route from Riga to Vilnius'\n"
        "  • 'Tallinn to Tartu, 100km per day'\n"
        "  • 'From Kaunas to Palanga with MTB'\n\n"
        "[dim]This version uses a pipeline optimized for local LLMs.[/dim]\n"
        "[dim]Type 'quit' to exit.[/dim]",
        title="Welcome",
        border_style="blue",
    ))
    
    while True:
        try:
            console.print()
            user_input = Prompt.ask("[bold green]You[/bold green]")
            
            if user_input.lower() in ["quit", "exit", "q"]:
                console.print("\n[dim]Goodbye! Happy trails! 🚴[/dim]\n")
                break
            
            if not user_input.strip():
                continue
            
            # Plan the route
            result = await plan_route(user_input)
            
            # Display result as markdown
            console.print()
            console.print(Markdown(result))
            
        except KeyboardInterrupt:
            console.print("\n\n[dim]Session interrupted. Goodbye![/dim]\n")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            import traceback
            traceback.print_exc()


async def single_query(query: str):
    """Run a single query."""
    result = await plan_route(query)
    console.print()
    console.print(Markdown(result))


def main():
    """Main entry point."""
    load_dotenv()
    
    # Ensure we're using Ollama
    if not os.getenv("USE_OLLAMA"):
        os.environ["USE_OLLAMA"] = "true"
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        asyncio.run(single_query(query))
    else:
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
