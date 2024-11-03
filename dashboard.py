import sqlite3
import json
from datetime import datetime

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%m/%d/%Y %I:%M:%S %p').year
    except:
        return None

def main():
    # Connect to the database
    conn = sqlite3.connect('crimes.db')
    cursor = conn.cursor()

    # Get distinct crime types
    cursor.execute("""
        SELECT DISTINCT `Primary Type`
        FROM filtered_crimes
        ORDER BY `Primary Type`
    """)
    crime_types = [row[0] for row in cursor.fetchall()]

    # Query to get the required fields including the Arrest column
    cursor.execute("""
        SELECT `Primary Type`, Latitude, Longitude, Date, Block, Description, Arrest
        FROM filtered_crimes
        WHERE Latitude IS NOT NULL 
        AND Longitude IS NOT NULL
    """)
    crimes = cursor.fetchall()
    
    # Process data and add arrest status
    crime_data = {}
    for crime_type in crime_types:
        crime_data[crime_type] = [
            {
                "lat": lat,
                "lng": lng,
                "date": date,
                "year": parse_date(date),
                "block": block,
                "description": desc,
                "arrest": "Yes" if arrest == 1 else "No"
            }
            for (ptype, lat, lng, date, block, desc, arrest) in crimes if ptype == crime_type
        ]

    conn.close()

    # HTML and JavaScript for the map
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Chicago Crime Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css"/>
    <style>
        body, html { 
            height: 100%; 
            margin: 0; 
            padding: 0;
            font-family: Arial, sans-serif;
        }
        #container {
            display: flex;
            height: 100vh;
        }
        #map { 
            flex: 1;
            height: 100%;
        }
        #controls {
            width: 300px;
            padding: 20px;
            background: white;
            overflow-y: auto;
            box-shadow: 2px 0 5px rgba(0,0,0,0.1);
        }
        .control-section {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .year-filter {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        .view-toggle {
            display: flex;
            gap: 10px;
            margin: 10px 0;
        }
        .view-toggle button {
            flex: 1;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            transition: all 0.2s;
        }
        .view-toggle button.active {
            background: #2c5282;
            color: white;
            border-color: #2c5282;
        }
        .view-toggle button:hover {
            background: #e0e0e0;
        }
        .view-toggle button.active:hover {
            background: #2a4365;
        }
        .crime-type {
            margin: 10px 0;
            padding: 8px;
            background: #f5f5f5;
            border-radius: 4px;
            transition: background-color 0.2s;
        }
        .crime-type:hover {
            background: #e0e0e0;
        }
        .crime-type label {
            cursor: pointer;
            display: flex;
            align-items: center;
        }
        .crime-type input[type="checkbox"] {
            margin-right: 10px;
        }
        h2, h3 {
            margin-top: 0;
            color: #333;
        }
        .count {
            margin-left: auto;
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div id="container">
        <div id="controls">
            <div class="control-section">
                <h2>Filters</h2>
                <select id="yearFilter" class="year-filter">
                    <option value="all">All Years</option>
                    <option value="2020">2020</option>
                    <option value="2021">2021</option>
                    <option value="2022">2022</option>
                    <option value="2023">2023</option>
                    <option value="2024">2024</option>
                </select>
                
                <div class="view-toggle">
                    <button id="pointsView" class="active">Points</button>
                    <button id="heatmapView">Heatmap</button>
                </div>
            </div>
            
            <div class="control-section">
                <h3>Crime Types</h3>
"""

    # Add checkboxes for each crime type
    for crime_type in crime_types:
        count = len(crime_data[crime_type])
        html += f"""
                <div class="crime-type">
                    <label>
                        <input type="checkbox" name="crime-toggle" value="{crime_type}">
                        {crime_type}
                        <span class="count">({count:,})</span>
                    </label>
                </div>
"""

    html += """
            </div>
        </div>
        <div id="map"></div>
    </div>
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
        // Initialize the map
        const map = L.map('map').setView([41.8781, -87.6298], 11);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // Crime data and layers
        const crimeData = """ + json.dumps(crime_data) + """;
        const layers = {};
        const heatmaps = {};
        let currentYear = 'all';
        let isHeatmapMode = false;

        function formatPopup(crime, crimeType) {
            return `
                <div class="popup-content">
                    <div class="popup-title">${crimeType}</div>
                    <div class="popup-detail"><strong>Date:</strong> ${crime.date}</div>
                    <div class="popup-detail"><strong>Location:</strong> ${crime.block}</div>
                    <div class="popup-detail"><strong>Details:</strong> ${crime.description || 'Not provided'}</div>
                    <div class="popup-detail"><strong>Arrest Made:</strong> ${crime.arrest}</div>
                </div>
            `;
        }

        function createHeatmapData(crimeType) {
            return crimeData[crimeType]
                .filter(crime => currentYear === 'all' || crime.year === parseInt(currentYear))
                .map(crime => [crime.lat, crime.lng, 1]);
        }

        function updateVisualization() {
            Object.keys(crimeData).forEach(crimeType => {
                const checkbox = document.querySelector(`input[value="${crimeType}"]`);
                if (checkbox.checked) {
                    // Remove existing layers
                    if (layers[crimeType]) map.removeLayer(layers[crimeType]);
                    if (heatmaps[crimeType]) map.removeLayer(heatmaps[crimeType]);

                    if (isHeatmapMode) {
                        // Create/update heatmap
                        heatmaps[crimeType] = L.heatLayer(createHeatmapData(crimeType), {
                            radius: 25,
                            blur: 15,
                            maxZoom: 15
                        }).addTo(map);
                    } else {
                        // Create/update point clusters
                        layers[crimeType] = L.markerClusterGroup({
                            maxClusterRadius: 50,
                            spiderfyOnMaxZoom: true,
                            showCoverageOnHover: false,
                            zoomToBoundsOnClick: true
                        });

                        crimeData[crimeType]
                            .filter(crime => currentYear === 'all' || crime.year === parseInt(currentYear))
                            .forEach(crime => {
                                L.marker([crime.lat, crime.lng])
                                    .bindPopup(formatPopup(crime, crimeType))
                                    .addTo(layers[crimeType]);
                            });

                        map.addLayer(layers[crimeType]);
                    }
                }
            });

            // Update counts
            Object.keys(crimeData).forEach(crimeType => {
                const count = crimeData[crimeType].filter(
                    crime => currentYear === 'all' || crime.year === parseInt(currentYear)
                ).length;
                const countSpan = document.querySelector(`input[value="${crimeType}"]`)
                    .parentElement.querySelector('.count');
                countSpan.textContent = `(${count.toLocaleString()})`;
            });
        }

        // Event Listeners
        document.getElementById('yearFilter').addEventListener('change', function(e) {
            currentYear = e.target.value;
            updateVisualization();
        });

        document.getElementById('pointsView').addEventListener('click', function() {
            if (!isHeatmapMode) return;
            isHeatmapMode = false;
            this.classList.add('active');
            document.getElementById('heatmapView').classList.remove('active');
            updateVisualization();
        });

        document.getElementById('heatmapView').addEventListener('click', function() {
            if (isHeatmapMode) return;
            isHeatmapMode = true;
            this.classList.add('active');
            document.getElementById('pointsView').classList.remove('active');
            updateVisualization();
        });

        document.querySelectorAll('input[name="crime-toggle"]').forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                const crimeType = this.value;
                if (!this.checked) {
                    if (layers[crimeType]) map.removeLayer(layers[crimeType]);
                    if (heatmaps[crimeType]) map.removeLayer(heatmaps[crimeType]);
                } else {
                    updateVisualization();
                }
            });
        });

        // Initial update
        updateVisualization();
    </script>
</body>
</html>
"""

    # Save the generated HTML to a file
    with open('crime_map.html', 'w') as f:
        f.write(html)

    print("\nMap has been generated as 'crime_map.html'")

if __name__ == '__main__':
    main()
