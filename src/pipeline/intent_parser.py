"""Simple intent parser for route planning requests.

This module uses a local LLM for ONE simple task: extracting structured
parameters from natural language. This is much easier for small models
than multi-step reasoning with tool calls.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class RouteIntent:
    """Parsed route planning intent from user input."""
    start_location: str
    end_location: str
    daily_distance_km: float = 80.0
    profile: str = "trekking"  # trekking, fastbike, mtb
    preferences: list[str] = None  # scenic, avoid_hills, etc.
    
    def __post_init__(self):
        if self.preferences is None:
            self.preferences = []


INTENT_PROMPT = """Extract route planning parameters from this request. Return ONLY valid JSON.

User request: "{user_input}"

Extract these fields:
- start_location: Starting city/place name (string)
- end_location: Destination city/place name (string)  
- daily_distance_km: Target km per day (number, default 80)
- profile: Bike type - "trekking", "fastbike", or "mtb" (default "trekking")

JSON response:"""


async def parse_route_intent(user_input: str) -> Optional[RouteIntent]:
    """
    Parse natural language into structured route intent.
    
    Uses local Ollama for simple extraction - much easier task than
    full agentic reasoning with tool calls.
    """
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model = os.getenv("MODEL_ID", "qwen2.5:7b")
    
    # Remove /v1 suffix if present (we use native Ollama API here)
    ollama_url = ollama_url.replace("/v1", "")
    
    prompt = INTENT_PROMPT.format(user_input=user_input)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temp for consistent extraction
                        "num_predict": 200,  # Short response expected
                    }
                },
                timeout=60.0,
            )
            
            if response.status_code != 200:
                return None
            
            result = response.json()
            text = result.get("response", "")
            
            # Extract JSON from response
            json_match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if not json_match:
                return None
            
            data = json.loads(json_match.group())
            
            return RouteIntent(
                start_location=data.get("start_location", ""),
                end_location=data.get("end_location", ""),
                daily_distance_km=float(data.get("daily_distance_km", 80)),
                profile=data.get("profile", "trekking"),
            )
            
        except Exception as e:
            print(f"Intent parsing error: {e}")
            return None


def parse_route_intent_simple(user_input: str) -> Optional[RouteIntent]:
    """
    Fallback regex-based parser for when LLM fails.
    
    Handles common patterns like:
    - "from Riga to Vilnius"
    - "Tallinn to Tartu, 100km per day"
    """
    text = user_input.lower()
    
    # Pattern: "from X to Y"
    match = re.search(r'from\s+([a-zA-ZäöüõšžÄÖÜÕŠŽāēīūĀĒĪŪ\s]+?)\s+to\s+([a-zA-ZäöüõšžÄÖÜÕŠŽāēīūĀĒĪŪ\s]+?)(?:\s*[,.]|\s+with|\s+daily|\s*$)', text)
    if match:
        start = match.group(1).strip().title()
        end = match.group(2).strip().title()
    else:
        # Pattern: "X to Y"
        match = re.search(r'^([a-zA-ZäöüõšžÄÖÜÕŠŽāēīūĀĒĪŪ\s]+?)\s+to\s+([a-zA-ZäöüõšžÄÖÜÕŠŽāēīūĀĒĪŪ\s]+?)(?:\s*[,.]|\s+with|\s+daily|\s*$)', text)
        if match:
            start = match.group(1).strip().title()
            end = match.group(2).strip().title()
        else:
            return None
    
    # Extract daily distance
    daily_km = 80.0
    km_match = re.search(r'(\d+)\s*(?:km|kilometers?)', text)
    if km_match:
        daily_km = float(km_match.group(1))
    
    # Extract profile
    profile = "trekking"
    if "mtb" in text or "mountain" in text:
        profile = "mtb"
    elif "fast" in text or "road" in text:
        profile = "fastbike"
    
    return RouteIntent(
        start_location=start,
        end_location=end,
        daily_distance_km=daily_km,
        profile=profile,
    )
