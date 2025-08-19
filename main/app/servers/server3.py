from mcp.server.fastmcp import FastMCP
from geopy.geocoders import Nominatim
import overpy
import requests

geolocator = Nominatim(user_agent="geo_assistant")
overpass_api = overpy.Overpass()

from dotenv import load_dotenv

load_dotenv()
# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.events']


# Initialize FastMCP server with the name "mytools"
mcp = FastMCP("geo_assistant")

@mcp.tool()
def get_coordinates(address):
    """
    Takes a human-readable location string and returns its latitude and longitude.
    """
    location = geolocator.geocode(address,timeout=15)

    if location:
        return location.latitude, location.longitude
    else:
        raise ValueError("Location not found. Please try a different address.")

@mcp.tool()
def find_nearby_places(address, place_type, radius_m):
    """
    Given the address, finds nearby places (nodes, ways, or relations) within the specified radius.
    """
    radius = int(radius_m)
    lat, lon = get_coordinates(address)

    query = f"""
    (
      node(around:{radius},{lat},{lon})["amenity"="{place_type}"];
      way(around:{radius},{lat},{lon})["amenity"="{place_type}"];
      relation(around:{radius},{lat},{lon})["amenity"="{place_type}"];
    );
    out center;
    """
    result = overpass_api.query(query)

    places = []
    for node in result.nodes:
        places.append((node.tags.get("name", "Unnamed"), node.lat, node.lon))
    for way in result.ways:
        if "name" in way.tags:
            places.append((way.tags["name"], way.center_lat, way.center_lon))
    for rel in result.relations:
        if "name" in rel.tags:
            places.append((rel.tags["name"], rel.center_lat, rel.center_lon))

    return places



@mcp.tool()
def get_travel_info(origin, destination):
    """
    Calculate distance and duration between origin and destination using OSRM API.
    """
    olat, olon = get_coordinates(origin)
    dlat, dlon = get_coordinates(destination)

    # Correct order: lon,lat
    url = f"https://router.project-osrm.org/route/v1/driving/{olon},{olat};{dlon},{dlat}?overview=false"

    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        route = data['routes'][0]
        distance_km = route['distance'] / 1000
        duration_min = route['duration'] / 60
        return distance_km, duration_min
    else:
        raise Exception(f"Error from OSRM API: {response.status_code} - {response.text}")


if __name__ == "__main__":
    mcp.run(transport="stdio")