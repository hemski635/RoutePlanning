#!/bin/bash
# Script to download BRouter segment data for a specific region

set -e

# Create data directories
mkdir -p brouter-data/segments4
mkdir -p brouter-data/profiles2

SEGMENTS_URL="https://brouter.de/brouter/segments4"

echo "BRouter Segment Downloader"
echo "=========================="
echo ""
echo "Segment files are 5x5 degree tiles named by their SW corner."
echo "Example: E5_N45.rd5 covers longitude 5-10°E, latitude 45-50°N"
echo ""

# Common European segments for bike packing
# Central Europe (Germany, Austria, Switzerland, etc.)
CENTRAL_EUROPE=(
    "E5_N45.rd5"   # Switzerland, Northern Italy
    "E5_N50.rd5"   # Germany (west), Belgium, Netherlands
    "E10_N45.rd5"  # Austria, Slovenia, Northern Italy
    "E10_N50.rd5"  # Germany (east), Czech Republic, Poland
    "E15_N45.rd5"  # Hungary, Croatia, Serbia
    "E15_N50.rd5"  # Poland, Slovakia
)

# Scandinavia
SCANDINAVIA=(
    "E5_N55.rd5"   # Denmark, Southern Sweden
    "E10_N55.rd5"  # Southern Sweden, Baltic
    "E5_N60.rd5"   # Norway, Sweden
    "E10_N60.rd5"  # Sweden, Finland
    "E15_N60.rd5"  # Finland, Baltic states
)

# Western Europe
WESTERN_EUROPE=(
    "W5_N35.rd5"   # Portugal, Spain (SW)
    "W5_N40.rd5"   # Portugal, Spain (NW)
    "E0_N40.rd5"   # Spain (NE), Southern France
    "W5_N45.rd5"   # France (west)
    "E0_N45.rd5"   # France (central)
    "W5_N50.rd5"   # UK, Ireland
    "E0_N50.rd5"   # UK, France (north), Belgium
)

download_segment() {
    local file=$1
    local dest="brouter-data/segments4/$file"
    
    if [ -f "$dest" ]; then
        echo "  [SKIP] $file (already exists)"
    else
        echo "  [DOWNLOAD] $file..."
        wget -q --show-progress -O "$dest" "$SEGMENTS_URL/$file" || {
            echo "  [ERROR] Failed to download $file"
            rm -f "$dest"
            return 1
        }
    fi
}

echo "Select region to download:"
echo "  1) Central Europe (Germany, Austria, Switzerland, Czech Republic)"
echo "  2) Scandinavia (Denmark, Sweden, Norway, Finland)"
echo "  3) Western Europe (UK, France, Spain, Portugal)"
echo "  4) All of the above"
echo "  5) Custom (enter segment names manually)"
echo ""
read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        echo ""
        echo "Downloading Central Europe segments..."
        for seg in "${CENTRAL_EUROPE[@]}"; do
            download_segment "$seg"
        done
        ;;
    2)
        echo ""
        echo "Downloading Scandinavia segments..."
        for seg in "${SCANDINAVIA[@]}"; do
            download_segment "$seg"
        done
        ;;
    3)
        echo ""
        echo "Downloading Western Europe segments..."
        for seg in "${WESTERN_EUROPE[@]}"; do
            download_segment "$seg"
        done
        ;;
    4)
        echo ""
        echo "Downloading all European segments..."
        for seg in "${CENTRAL_EUROPE[@]}" "${SCANDINAVIA[@]}" "${WESTERN_EUROPE[@]}"; do
            download_segment "$seg"
        done
        ;;
    5)
        echo ""
        echo "Enter segment filenames (e.g., E10_N50.rd5), one per line."
        echo "Enter empty line when done:"
        while true; do
            read -p "> " seg
            [ -z "$seg" ] && break
            download_segment "$seg"
        done
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Download complete!"
echo ""
echo "To start BRouter, run:"
echo "  docker-compose up -d"
echo ""
echo "BRouter will be available at: http://localhost:17777"
