"""Main route planning agent."""

import os
from typing import Any

from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient
from openai import AsyncOpenAI

from src.tools.routing import calculate_route, get_route_elevation, geocode_location
from src.tools.camping import find_daily_camping_spots
from src.tools.poi import find_points_of_interest, find_scenic_route_spots
from src.tools.export import generate_brouter_web_url, export_route_gpx


SYSTEM_INSTRUCTIONS = """You are a bike packing route planner.

## Process
1. `geocode_location` for start/end points
2. `calculate_route` to get initial route waypoints
3. `find_daily_camping_spots` with waypoints and daily_distance_km
4. Use `route_waypoints` from camping result to `calculate_route` again - this gives routed path through camps
5. `generate_brouter_web_url` with final waypoints and `camp_pois` from camping result

## Key Rule
Each day's route ENDS at a camping spot. Use the `route_waypoints` from `find_daily_camping_spots` to recalculate the actual route - this ensures the route goes THROUGH each camping location.

## Output
For each day: start point, end point (camp), approx distance.
End with the interactive map link (from tool only).
"""


def create_route_planner_agent(
    github_token: str | None = None,
    model_id: str | None = None,
    use_ollama: bool = False,
) -> ChatAgent:
    """
    Create and configure the route planning agent.
    
    Args:
        github_token: GitHub personal access token for model access.
                     Falls back to GITHUB_TOKEN environment variable.
        model_id: Model to use. Falls back to MODEL_ID env var or defaults to gpt-4.1
        use_ollama: If True, use local Ollama instead of GitHub Models.
                   Can also be set via USE_OLLAMA=true environment variable.
    
    Returns:
        Configured ChatAgent instance
    """
    # Check if using Ollama (local LLM)
    use_ollama = use_ollama or os.getenv("USE_OLLAMA", "").lower() in ("true", "1", "yes")
    
    if use_ollama:
        # Local Ollama setup
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/v1")
        model = model_id or os.getenv("MODEL_ID", "qwen2.5:7b")
        
        openai_client = AsyncOpenAI(
            base_url=ollama_url,
            api_key="ollama",  # Ollama doesn't need a real key
        )
    else:
        # GitHub Models setup
        token = github_token or os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable "
                "or pass github_token parameter. Get a token at: "
                "https://github.com/settings/tokens"
            )
        
        model = model_id or os.getenv("MODEL_ID", "openai/gpt-4.1")
        
        openai_client = AsyncOpenAI(
            base_url="https://models.github.ai/inference",
            api_key=token,
        )
    
    # Create chat client
    chat_client = OpenAIChatClient(
        async_client=openai_client,
        model_id=model,
    )
    
    # Create agent with tools
    agent = ChatAgent(
        chat_client=chat_client,
        name="RoutePlannerAgent",
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[
            # Routing tools
            calculate_route,
            get_route_elevation,
            geocode_location,
            # Camping tools
            find_daily_camping_spots,
            # POI tools
            find_points_of_interest,
            find_scenic_route_spots,
            # Export tools
            generate_brouter_web_url,
            export_route_gpx,
        ],
    )
    
    return agent
