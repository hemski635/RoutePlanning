"""Main entry point for the bike packing route planner."""

import asyncio
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from src.agents import create_route_planner_agent
from src.config import settings


console = Console()


async def chat_loop():
    """Run an interactive chat session with the route planner agent."""
    
    # Check configuration
    missing = settings.validate_required()
    if missing:
        console.print(Panel(
            f"[red]Missing required configuration:[/red]\n" +
            "\n".join(f"  • {m}" for m in missing) +
            "\n\n[dim]Copy .env.example to .env and fill in your API keys.[/dim]",
            title="Configuration Error",
            border_style="red",
        ))
        sys.exit(1)
    
    # Create agent
    console.print("\n[bold blue]🚴 Bike Packing Route Planner[/bold blue]\n")
    console.print("[dim]Initializing agent...[/dim]")
    
    try:
        agent = create_route_planner_agent()
    except Exception as e:
        console.print(f"[red]Failed to create agent: {e}[/red]")
        sys.exit(1)
    
    console.print("[green]✓ Agent ready![/green]\n")
    
    # Print welcome message
    console.print(Panel(
        "I'm your bike packing route planning assistant! I can help you plan "
        "multi-day cycling adventures with:\n\n"
        "• Route calculation with surface preferences\n"
        "• Camping site recommendations\n"
        "• Scenic viewpoints and rest stops\n"
        "• Day-by-day itinerary with GPS coordinates\n\n"
        "[dim]Type 'quit' or 'exit' to end the session.[/dim]",
        title="Welcome",
        border_style="blue",
    ))
    
    # Create a thread for conversation continuity
    thread = agent.get_new_thread()
    
    while True:
        try:
            # Get user input
            console.print()
            user_input = Prompt.ask("[bold green]You[/bold green]")
            
            if user_input.lower() in ["quit", "exit", "q"]:
                console.print("\n[dim]Goodbye! Happy trails! 🚴[/dim]\n")
                break
            
            if not user_input.strip():
                continue
            
            # Stream agent response
            console.print("\n[bold blue]Agent[/bold blue]:", end=" ")
            
            full_response = ""
            async for chunk in agent.run_stream(user_input, thread=thread):
                if chunk.text:
                    console.print(chunk.text, end="")
                    full_response += chunk.text
            
            console.print()  # New line after response
            
        except KeyboardInterrupt:
            console.print("\n\n[dim]Session interrupted. Goodbye![/dim]\n")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            console.print("[dim]Please try again.[/dim]")


async def single_query(query: str):
    """Run a single query and print the response."""
    
    agent = create_route_planner_agent()
    
    console.print(f"\n[bold green]Query:[/bold green] {query}\n")
    console.print("[bold blue]Agent:[/bold blue]", end=" ")
    
    async for chunk in agent.run_stream(query):
        if chunk.text:
            console.print(chunk.text, end="")
    
    console.print()


def main():
    """Main entry point."""
    load_dotenv()
    
    if len(sys.argv) > 1:
        # Single query mode
        query = " ".join(sys.argv[1:])
        asyncio.run(single_query(query))
    else:
        # Interactive chat mode
        asyncio.run(chat_loop())


if __name__ == "__main__":
    main()
