# Bike Packing Route Planning Agent - High-Level Development Plan

## 1. Project Overview

An AI agent system that helps plan bike packing routes by considering:
- **Inputs**: Surface preferences, start/end points, daily distance targets
- **Outputs**: GPS coordinates for route, camping sites, and scenic pause spots

---

## 2. Architecture Design

### Option A: Single Agent with Multiple Tools
A unified agent that orchestrates all planning tasks using specialized tools.

```
┌─────────────────────────────────────────────────────────┐
│                   Route Planning Agent                   │
│  (Orchestrates route planning with function calling)     │
├─────────────────────────────────────────────────────────┤
│  Tools:                                                  │
│  ├── route_calculator      (routing & distances)        │
│  ├── surface_analyzer      (road surface types)         │
│  ├── camping_finder        (campsites & wild camping)   │
│  ├── poi_finder            (scenic spots, water, food)  │
│  └── elevation_analyzer    (terrain difficulty)         │
└─────────────────────────────────────────────────────────┘
```

### Option B: Multi-Agent System (Recommended for complexity)
Specialized agents working together for better accuracy and maintainability.

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent                        │
│     (Coordinates workflow, handles user interaction)         │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ Route Agent   │  │ Camping Agent │  │ POI Agent     │
│               │  │               │  │               │
│ - Pathfinding │  │ - Campsites   │  │ - Scenic spots│
│ - Surfaces    │  │ - Wild camp   │  │ - Water/food  │
│ - Elevation   │  │ - Shelters    │  │ - Rest areas  │
└───────────────┘  └───────────────┘  └───────────────┘
```

---

## 3. Technology Stack

### AI Framework
- **SDK**: Microsoft Agent Framework (Python)
  - Supports multi-agent orchestration
  - Function calling for external API integration
  - MCP (Model Context Protocol) support
  
```bash
pip install agent-framework-azure-ai --pre
```
> ⚠️ The `--pre` flag is required while Agent Framework is in preview

### Recommended AI Model
For development/prototyping:
- **GitHub Models** (free tier): `openai/gpt-4.1` or `openai/gpt-4o`
  - Good function calling support
  - Free to start, sufficient for development
  
For production:
- **Microsoft Foundry**: `gpt-4.1` or `gpt-5-mini`
  - Better rate limits and reliability
  - Larger context window for complex routes

### External APIs & Data Sources

| Purpose | Options |
|---------|---------|
| **Routing** | OpenRouteService, GraphHopper, OSRM (OpenStreetMap) |
| **Surface Data** | OpenStreetMap tags, Waymarked Trails |
| **Camping** | OpenCampingMap, park-sleep.com API, iOverlander |
| **Elevation** | OpenTopoData, Mapbox Terrain |
| **POI Data** | Overpass API (OSM), Google Places (paid) |

---

## 4. Core Features (MVP)

### 4.1 User Input Schema
```python
class RouteRequest:
    start_point: tuple[float, float]      # (lat, lon)
    end_point: tuple[float, float]        # (lat, lon)
    surface_preferences: list[str]        # ["paved", "gravel", "trail"]
    daily_distance_km: float              # Target daily distance
    trip_days: int | None                 # Optional: fixed trip length
    avoid: list[str]                      # ["highways", "busy_roads"]
```

### 4.2 Output Schema
```python
class RouteOutput:
    total_distance_km: float
    estimated_days: int
    daily_segments: list[DailySegment]
    
class DailySegment:
    day_number: int
    start_coords: tuple[float, float]
    end_coords: tuple[float, float]
    distance_km: float
    elevation_gain_m: float
    surface_breakdown: dict[str, float]   # {"gravel": 60, "paved": 40}
    camping_options: list[CampingSite]
    pause_spots: list[POI]
    gpx_track: str                        # GPX format string

class CampingSite:
    coords: tuple[float, float]
    name: str
    type: str                             # "campground", "wild", "shelter"
    amenities: list[str]
    rating: float | None
    booking_url: str | None

class POI:
    coords: tuple[float, float]
    name: str
    category: str                         # "viewpoint", "water", "food", "rest"
    description: str
```

---

## 5. Development Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Set up project structure
- [ ] Configure AI model access (GitHub Models for dev)
- [ ] Create basic agent with chat capabilities
- [ ] Implement routing tool (OpenRouteService integration)
- [ ] Basic GPX generation

### Phase 2: Core Features (Week 3-4)
- [ ] Surface preference filtering
- [ ] Daily segment calculation
- [ ] Camping site finder tool
- [ ] Elevation analysis tool
- [ ] Multi-option camping recommendations

### Phase 3: Enhancement (Week 5-6)
- [ ] POI/scenic spot finder
- [ ] Route optimization (avoid backtracking)
- [ ] Weather consideration (optional)
- [ ] Multi-agent orchestration (if needed)
- [ ] Interactive refinement (user feedback loop)

### Phase 4: Polish (Week 7-8)
- [ ] Error handling & fallbacks
- [ ] Caching for API calls
- [ ] Export formats (GPX, KML, GeoJSON)
- [ ] Basic UI (CLI or simple web)
- [ ] Testing with real routes

---

## 6. Project Structure

```
routeplanning/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # Main coordinator agent
│   │   ├── route_agent.py       # Route planning specialist
│   │   └── camping_agent.py     # Camping/POI specialist
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── routing.py           # OpenRouteService integration
│   │   ├── camping.py           # Camping site APIs
│   │   ├── poi.py               # Points of interest
│   │   └── elevation.py         # Elevation data
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py           # Input models
│   │   └── response.py          # Output models
│   └── utils/
│       ├── __init__.py
│       ├── gpx.py               # GPX generation
│       └── geo.py               # Geo calculations
├── tests/
├── config/
│   └── settings.py
├── docs/
├── requirements.txt
├── .env.example
└── main.py
```

---

## 7. Key Decisions to Make

| Decision | Options | Recommendation |
|----------|---------|----------------|
| Single vs Multi-Agent | Single agent simpler; Multi-agent more maintainable | Start single, refactor if needed |
| Routing API | OpenRouteService (free), GraphHopper, OSRM | OpenRouteService (bike profiles) |
| Camping Data | OpenCampingMap, iOverlander, custom DB | OpenCampingMap + OSM Overpass |
| Model Host | GitHub (free), Microsoft Foundry (production) | GitHub for dev, Foundry for prod |
| Surface Data | OSM tags only vs specialized APIs | OSM tags (sufficient for MVP) |

---

## 8. API Keys & Services Needed

1. **AI Model Access**
   - GitHub Personal Access Token (for GitHub Models)
   - Or: Microsoft Foundry API key

2. **Routing**
   - OpenRouteService API key (free tier: 2000 req/day)

3. **Maps/POI**
   - Overpass API (no key needed, but rate limited)
   - Optional: Mapbox token for better elevation

---

## 9. Next Steps

1. **Confirm architecture choice** (single vs multi-agent)
2. **Set up development environment**
3. **Register for required API keys**
4. **Create initial project structure**
5. **Implement first tool** (basic routing)
6. **Build minimal agent** that can plan a simple route

---

## 10. Example Interaction

```
User: Plan a 5-day bike packing trip from Munich to Vienna. 
      I prefer gravel roads and want to ride about 80km per day.

Agent: I'll plan your Munich to Vienna bike packing route!

📍 Route Overview:
- Total Distance: 420 km
- Days: 5
- Surface: 65% gravel, 30% paved, 5% trail

📅 Day 1: Munich → Wasserburg am Inn (78 km)
- Start: 48.1351, 11.5820
- End: 48.0614, 12.2311
- Elevation: +450m / -380m
- 🏕️ Camping Options:
  1. Campingplatz Wasserburg (48.0598, 12.2287) ⭐ 4.2
  2. Wild camping spot by Inn River (48.0631, 12.2156)
- ☕ Nice Stops:
  - Marktl am Inn viewpoint (48.2544, 12.8456)
  - Gasthaus zur Post (lunch) (48.1234, 12.0567)

[... continues for each day ...]

Would you like me to:
1. Adjust the daily distances?
2. Show more camping options?
3. Export as GPX file?
```

---

## Resources

- [Microsoft Agent Framework Docs](https://github.com/microsoft/agent-framework)
- [OpenRouteService API](https://openrouteservice.org/dev/#/api-docs)
- [Overpass API (OSM)](https://overpass-turbo.eu/)
- [OpenCampingMap](https://opencampingmap.org/)
