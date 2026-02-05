#!/bin/bash
# Setup script for brouter-web frontend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BROUTER_WEB_DIR="$PROJECT_DIR/brouter-web"

echo "Setting up brouter-web..."

# Clone brouter-web if not exists
if [ ! -d "$BROUTER_WEB_DIR" ]; then
    echo "Cloning brouter-web repository..."
    git clone --depth 1 https://github.com/nrenner/brouter-web.git "$BROUTER_WEB_DIR"
else
    echo "brouter-web directory already exists, skipping clone"
fi

cd "$BROUTER_WEB_DIR"

# Create config.js pointing to local BRouter
echo "Creating config.js..."
cat > config.js << 'EOF'
(function () {
    // BRouter server - points to our local Docker container
    BR.conf.host = 'http://localhost:17777';
    
    // Profile directory (served by BRouter)
    BR.conf.profilesUrl = 'http://localhost:17777/profiles/';
    
    // Default profile
    BR.conf.defaultProfile = 'trekking';
    
    // Map layers
    BR.conf.defaultLayer = 'OpenStreetMap';
    
    // Routing options
    BR.conf.defaultAlternatives = 0;
    
    // Export options
    BR.conf.defaultFormat = 'gpx';
})();
EOF

# Create keys.js (empty - no API keys needed for basic usage)
echo "Creating keys.js..."
cat > keys.js << 'EOF'
(function () {
    // API keys for additional map layers (optional)
    // BR.keys.bing = 'your-bing-key';
    // BR.keys.digitalGlobe = 'your-digitalglobe-key';
    // BR.keys.thunderforest = 'your-thunderforest-key';
    // BR.keys.esri = 'your-esri-key';
})();
EOF

echo ""
echo "✓ brouter-web setup complete!"
echo ""
echo "Next steps:"
echo "  1. Build and start services: docker compose up -d --build"
echo "  2. Open http://localhost:8080 in your browser"
echo ""
