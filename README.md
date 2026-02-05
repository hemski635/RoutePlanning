# 🚴 Bike Packing Route Planner

An AI-powered agent that helps plan multi-day bike packing routes with camping recommendations, remote wild camping spots, and points of interest.

Built with [Microsoft Agent Framework](https://github.com/microsoft/agents) and powered by self-hosted routing services.

## Features

- **🗺️ Route Planning**: Calculate cycling routes with surface type preferences (paved, gravel, trail)
- **📅 Daily Segments**: Automatically divide routes into daily segments based on your target distance
- **🏕️ Camping Sites**: Find campsites, shelters, and official camping grounds
- **🌲 Wild Camping**: Discover remote spots in large forest areas (20+ hectares)
- **🔭 Points of Interest**: Viewpoints, water sources, food stops, and bike shops
- **📍 GPS Coordinates**: Get precise coordinates for all waypoints
- **📤 GPX Export**: Export routes for use in GPS devices and apps
- **🌐 BRouter Web**: Visual route planning with interactive map
- **🏠 Fully Local**: Run 100% offline with local LLM (Ollama)

## Two Modes of Operation

### 1. Cloud Mode (GitHub Models)
Full agentic AI with multi-step reasoning. Best for complex queries.
```bash
python main.py
```

### 2. Local Mode (Ollama) ⭐ Recommended
Pipeline-based approach optimized for local LLMs. Faster and more reliable.
```bash
python main_local.py
```

| Mode | LLM | Speed | Offline | Complex Queries |
|------|-----|-------|---------|-----------------|
| Cloud | GPT-4.1 | Fast | No | Yes |
| Local | Qwen 2.5 7B | Medium | Yes | Simple only |

## Infrastructure Options

### Option A: Public Services (Zero Setup) ⭐ Easy Start

Use public BRouter, brouter-web, and Overpass API instances. No local setup required!

**Pros:** No Docker, no downloads, instant start  
**Cons:** Rate limits apply, requires internet, may be slower

```bash
# In .env, set:
USE_PUBLIC_SERVICES=true
```

Then just run:
```bash
python main_local.py "Plan a route from Riga to Tallinn"
```

### Option B: Self-Hosted Services (Recommended for heavy use)

Run your own BRouter and Overpass instances for unlimited queries and offline capability.

**Pros:** Fast, no rate limits, works offline, full data control  
**Cons:** Requires ~10GB disk space and initial setup

```bash
# In .env, set:
USE_PUBLIC_SERVICES=false
```

See [Setup Local Services](#3-download-routing-data) section below.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AI Agent      │────▶│    BRouter      │────▶│  Routing Data   │
│  (Local/Cloud)  │     │ (local/public)  │     │   (segments4)   │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │
        ▼
┌─────────────────┐     ┌─────────────────┐
│  Overpass API   │────▶│    OSM Data     │
│ (local/public)  │     │  (POI queries)  │
│                 │     │                 │
└─────────────────┘     └─────────────────┘

Public Services:
- BRouter: https://brouter.de/brouter
- brouter-web: https://brouter.de/brouter-web  
- Overpass: https://overpass-api.de/api/interpreter

Local Services (Docker):
- BRouter: http://localhost:17777
- brouter-web: http://localhost:8080
- Overpass: http://localhost:12345
```

## Quick Start

### Prerequisites

**Minimal setup (public services):**
- Python 3.11+
- Internet connection

**Full local setup (self-hosted services):**
- Python 3.11+
- Docker & Docker Compose
- **~10GB disk space** for data:
  - BRouter segments: ~250MB (Baltic states)
  - OSM data: ~1.5GB (Baltic states PBF + BZ2)
  - Overpass database: ~6GB (generated from OSM)
- For **Local LLM mode**: Additional ~5GB for Ollama + Qwen 2.5 7B model
- **Optional**: GitHub account (only for cloud API mode)

### 1. Clone and Setup Environment

```bash
git clone <repo-url> routeplanning
cd routeplanning

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your GitHub token:

```env
# Required: GitHub Personal Access Token
# Create at: https://github.com/settings/tokens
# Needs no special permissions for GitHub Models
GITHUB_TOKEN=ghp_your_token_here

# Model to use (default works well)
MODEL_ID=openai/gpt-4.1

# Routing services (defaults work with Docker setup)
BROUTER_URL=http://localhost:17777
OVERPASS_URL=http://localhost:12345/api/interpreter
```

### 3. Download Routing Data

BRouter needs segment files for the regions you want to route through.

```bash
# Make script executable
chmod +x scripts/download_segments.sh

# Run and select your region
./scripts/download_segments.sh
```

**Manual download** (if script fails):
1. Go to https://brouter.de/brouter/segments4/
2. Download `.rd5` files for your region (e.g., `E20_N50.rd5` for Baltic states)
3. Place in `brouter-data/segments4/`

Segment naming: Files are named by SW corner of 5°×5° tile.
- `E20_N50.rd5` = Longitude 20-25°E, Latitude 50-55°N (covers Lithuania, Latvia, parts of Poland/Belarus)
- `E20_N55.rd5` = Covers Estonia, parts of Latvia, Finland

### 4. Setup Local Overpass API (OSM Data)

For camping spot searches, we use a local Overpass API instance to avoid rate limiting.

#### Download OSM Data for Baltic States

```bash
mkdir -p osm-data

# Download Baltic countries from Geofabrik
wget -O osm-data/estonia.osm.pbf https://download.geofabrik.de/europe/estonia-latest.osm.pbf
wget -O osm-data/latvia.osm.pbf https://download.geofabrik.de/europe/latvia-latest.osm.pbf
wget -O osm-data/lithuania.osm.pbf https://download.geofabrik.de/europe/lithuania-latest.osm.pbf

# Install osmium-tool for merging/converting
sudo apt install osmium-tool  # or: brew install osmium-tool

# Merge all three countries into one file
osmium merge osm-data/estonia.osm.pbf osm-data/latvia.osm.pbf osm-data/lithuania.osm.pbf -o osm-data/baltic-states.osm.pbf

# Convert to bz2 format (required by Overpass image)
osmium cat osm-data/baltic-states.osm.pbf -o osm-data/baltic-states.osm.bz2
```

**Other regions:**
- Full Europe: https://download.geofabrik.de/europe.html
- Poland: `https://download.geofabrik.de/europe/poland-latest.osm.pbf`
- Germany: `https://download.geofabrik.de/europe/germany-latest.osm.pbf`
- All regions: https://download.geofabrik.de/

#### Use a different region

If using a different region, update the volume mount in `docker-compose.yml`:

```yaml
overpass:
  volumes:
    - ./osm-data/your-region.osm.bz2:/data/planet.osm.bz2:ro
```

### 5. Start Services

```bash
# Start all services (first run takes 5-15 min for Overpass import)
docker compose up -d

# Check status
docker compose ps

# View Overpass import progress
docker logs -f overpass
```

Wait until you see in the Overpass logs:
```
Database created. Now updating it.
Generating areas...
```

### 6. (Optional) Setup Ollama for Local LLM

For fully offline operation, install Ollama:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download Qwen 2.5 7B (best tool-calling model for CPU)
ollama pull qwen2.5:7b

# Verify it's running
curl http://localhost:11434/v1/models
```

Configure `.env` for local mode:
```env
USE_OLLAMA=true
OLLAMA_URL=http://localhost:11434/v1
MODEL_ID=qwen2.5:7b
```

Then use the local mode entry point:
```bash
python main_local.py
```

**Performance note:** On CPU-only systems, expect ~2-5 tokens/second.
The pipeline-based `main_local.py` minimizes LLM calls for better performance.

#### Verify Services

```bash
# Test BRouter
curl "http://localhost:17777/brouter?lonlats=25.2797,54.6872|24.1052,56.9494&profile=trekking&format=geojson" | head -5

# Test Overpass
curl -X POST "http://localhost:12345/api/interpreter" \
  -d 'data=[out:json];node["tourism"="camp_site"](54.5,25.0,54.8,25.5);out body 3;'
```

### 6. Run the Planner

```bash
# Activate virtual environment
source .venv/bin/activate

# Interactive mode
python main.py

# Single query
python main.py "Plan a 3-day gravel bike trip from Vilnius to Riga"
```

## Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| `brouter` | 17777 | Cycling route calculation |
| `overpass` | 12345 | OSM data queries (camping, POI) |
| `brouter-web` | 8080 | Visual route planning UI |

### Service Management

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart specific service
docker compose restart brouter

# View logs
docker compose logs -f overpass

# Check disk usage
docker system df
```

### BRouter Web Interface

Access the visual route planner at http://localhost:8080

Features:
- Click to add waypoints
- Drag routes to adjust
- Choose routing profiles (trekking, gravel, racing)
- Export GPX files

## Example Interaction

```
You: Plan a 5-day bike packing trip from Vilnius to Riga.
     I prefer gravel roads and want to ride about 80km per day.
     Find me remote wild camping spots away from towns.

Agent: I'll plan your Vilnius to Riga bike packing route!

📍 Route Overview:
- Total Distance: 310 km
- Days: 4
- Surface: 60% gravel, 35% paved, 5% trail

📅 Day 1: Vilnius → Širvintos area (78 km)
- Start: 54.6872, 25.2797
- End: 55.0412, 24.9567
- Elevation: +320m / -280m

🏕️ Remote Camping Spots (2km+ from settlements):
1. Forest shelter near Labanoras (55.0234, 25.1456)
   - Type: Lean-to shelter
   - Remoteness: 3.2km from nearest village
   - Water: Stream 200m south

2. Viewpoint clearing (55.0567, 24.8901)
   - Type: Open meadow
   - Remoteness: 2.8km from road
   - Notes: Good for hammock, tree cover

[... continues for each day ...]
```

## Project Structure

```
routeplanning/
├── src/
│   ├── agents/              # AI agent definitions
│   │   └── route_planner.py
│   ├── tools/               # Agent tools
│   │   ├── routing.py       # BRouter integration
│   │   ├── camping.py       # Camping & wild spots finder
│   │   ├── poi.py           # Points of interest
│   │   └── export.py        # GPX export, BRouter Web URLs
│   └── utils/               # Utilities
│       ├── gpx.py           # GPX file handling
│       └── geo.py           # Geo calculations
├── brouter-data/
│   ├── segments4/           # Routing segment files (.rd5)
│   └── profiles2/           # Custom routing profiles
├── osm-data/                # OSM data files for Overpass
├── overpass-data/           # Overpass database (auto-generated)
├── output/                  # Generated GPX files
├── scripts/
│   ├── download_segments.sh # Download routing data
│   └── setup_brouter_web.sh # Setup web interface
├── docker-compose.yml       # Service definitions
├── requirements.txt         # Python dependencies
├── main.py                  # Entry point
└── .env                     # Configuration (create from .env.example)
```

## Tool Functions

### Routing (`src/tools/routing.py`)

- `calculate_route(start, end, profile)` - Calculate route between points
- `get_route_elevation(route)` - Get elevation profile
- `geocode_location(name)` - Convert place name to coordinates

### Camping (`src/tools/camping.py`)

- `find_daily_camping_spots(waypoints, daily_km, radius)` - Find one camping spot per day, evenly distributed along route (max 10km from each day's end point)

### Export (`src/tools/export.py`)

- `export_route_gpx(route_data, filename)` - Generate GPX file
- `generate_brouter_web_url(waypoints, profile, pois)` - Create shareable route URL with camp markers

## Configuration Options

### Routing Profiles

BRouter supports multiple routing profiles:

| Profile | Best For |
|---------|----------|
| `trekking` | General touring, mixed surfaces |
| `fastbike` | Road cycling, speed priority |
| `safety` | Avoid traffic, family-friendly |
| `shortest` | Minimum distance |
| `moped` | Moped/scooter routing |

### Wild Camping Filters

The camping tool filters spots to be:
- **500m+ from major roads** (motorway, trunk, primary, secondary)
- **2km+ from settlements** (cities, towns, villages)
- Near **water sources** when possible

## Troubleshooting

### BRouter returns "no route found"

1. Check segment files exist: `ls brouter-data/segments4/`
2. Verify segments cover your area (check coordinates)
3. Download missing segments from https://brouter.de/brouter/segments4/

### Overpass returns empty results

1. Check container is running: `docker ps`
2. Verify import completed: `docker logs overpass | tail -20`
3. Test simple query:
   ```bash
   curl -X POST "http://localhost:12345/api/interpreter" \
     -d 'data=[out:json];node(1);out;'
   ```

### "Rate limit exceeded" errors

If using public Overpass API, switch to local:

1. Setup local Overpass (see step 4)
2. Set in `.env`: `OVERPASS_URL=http://localhost:12345/api/interpreter`

### Docker disk space issues

```bash
# Check usage
docker system df

# Clean unused data
docker system prune -a

# Remove Overpass database to reimport
rm -rf overpass-data/*
docker compose restart overpass
```

## API Dependencies

| Service | Purpose | Notes |
|---------|---------|-------|
| [GitHub Models](https://github.com/marketplace/models) | AI model (GPT-4.1) | Free tier available |
| [BRouter](https://github.com/abrensch/brouter) | Cycling routes | Self-hosted (Docker) |
| [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) | OSM queries | Self-hosted (Docker) |
| [Geofabrik](https://download.geofabrik.de/) | OSM data downloads | Free |

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Adding New Tools

1. Create function in `src/tools/`
2. Use `Annotated` types for parameters
3. Add descriptive docstring
4. Register in `src/agents/route_planner.py`

Example:
```python
async def my_new_tool(
    location: Annotated[str, "Location as 'lat,lon'"],
    radius_km: Annotated[float, "Search radius in km"] = 5.0,
) -> str:
    """Find something useful near a location."""
    # Implementation
    return json.dumps(results)
```

## License

MIT
