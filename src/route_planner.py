import openrouteservice
import os
import geopandas as gpd
import pyproj
import threading
import time
from shapely.geometry import Polygon, LineString, mapping
from shapely.ops import transform


class RoutePlanner:
    def __init__(self, accident_service):
        self.client = self.connect_to_api()
        self.accident_service = accident_service
        self.accident_areas = self.accident_service.get_accident_areas()
        self.previous_route = None

        self.start_check_new_accidents_thread()

    def connect_to_api(self):
        api_key = os.getenv("OPENROUTESERVICE_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTESERVICE_API_KEY is not set in the .env file.")
        try:
            client = openrouteservice.Client(key=api_key)
            return client
        except openrouteservice.exceptions.ApiError as e:
            raise ValueError(f"Could not connect to OpenRouteService API: {e}")
        except Exception as e:
            raise ValueError(f"An unexpected error occurred: {e}")

    def get_accident_areas(self):
        return self.accident_areas

    def update_accident_areas(self):
        self.accident_areas = self.accident_service.get_accident_areas()

    def save_requested_route(self, start_coords, end_coords, preference):
        self.previous_route = (start_coords, end_coords, preference)

    def start_check_new_accidents_thread(self):
        update_thread = threading.Thread(target=self.check_for_new_accidents)
        update_thread.daemon = True
        update_thread.start()

    def check_for_new_accidents(self):
        """
        checks if there are new accidents
        if new accident comes, check the previously requested route and update it so it avoids the new accident
        """
        while True:
            self.update_accident_areas()
            new_accident = self.accident_service.get_new_accident()
            self.accident_service.clear_new_accident()

            if new_accident is not None:
                self.accident_areas = self.accident_service.get_accident_areas()
                previous_route = self.previous_route
                if previous_route is not None:
                    start_coords, end_coords, preference = previous_route
                    accident_on_previous_route = self.is_new_accident_on_previous_route(
                        start_coords, end_coords, new_accident
                    )
                    if accident_on_previous_route:
                        self.update_route(start_coords, end_coords, preference)
            time.sleep(3)

    def is_new_accident_on_previous_route(self, start_coords, end_coords, new_accident):
        intersections = self.get_accidents_on_route(
            start_coords, end_coords, [new_accident]
        )
        return not intersections.empty

    def update_route(self, start_coords, end_coords, preference=None):
        updated_route = self.get_route(start_coords, end_coords, preference)
        if updated_route is not None:
            # Add updated:True to route object to distinguish from regular routes
            updated_route = {"updated": True, **updated_route}
            self.accident_service.send_updated_route(updated_route)
            print("Updated route sent to avoid new accident.")

    def get_route(
        self,
        start_coords: tuple,
        end_coords: tuple,
        preference: bool = None,
    ):
        """
        Parameters:
        - start_coord: Starting coordinate of the route as a tuple (longitude, latitude).
        - end_coord: Ending coordinate of the route as a tuple (longitude, latitude).
        """
        if self.client is None:
            print("Unable to connect to the API.")
            return

        # save route so it can be updated later if there is a new accident
        self.save_requested_route(start_coords, end_coords, preference)

        params = self.get_route_params(start_coords, end_coords, preference)

        try:
            if params is None:
                return
            route = self.client.directions(**params)
            return route
        except Exception as e:
            print(f"An error occurred during the routing request: {e}")

    def get_route_params(
        self,
        start_coord: tuple,
        end_coord: tuple,
        preference: str = None,
    ):
        params = {
            "coordinates": [start_coord, end_coord],
            "profile": "driving-car",
            "format": "geojson",
            "instructions": True,
        }

        if preference is not None:
            params["preference"] = preference

        accident_areas = self.get_accident_areas()
        intersections = intersections = self.get_accidents_on_route(
            start_coord, end_coord, accident_areas
        )

        if not intersections.empty:
            # This should create a list of lists for MultiPolygon coordinates
            buffered_polygons = self.create_buffered_polygons_for_intersections(
                intersections, buffer_distance_meters=10
            )
            avoid_polygons_geojson = {
                "type": "MultiPolygon",
                "coordinates": buffered_polygons,
            }
            params["options"] = {"avoid_polygons": avoid_polygons_geojson}

        return params

    def get_accidents_on_route(self, start_coord: tuple, end_coord: tuple, accidents):
        """
        Checks if there are accident areas intersecting with the route
        defined by start and end coordinates.

        Parameters:
        - start_coord: Starting coordinate of the route as a tuple (longitude, latitude).
        - end_coord: Ending coordinate of the route as a tuple (longitude, latitude).

        Returns:
        - intersections: A GeoDataFrame of intersecting accident polygons, if any.

        Limitation: Checks the intersections for the straight route from start to end point, e.g. bird-route,
        not for the actual full route. Only avoids accidents that intersect with that line.
        """
        accident_polygons = [Polygon(coords) for coords in accidents]
        route = LineString([start_coord, end_coord])

        # Check if accidents intersect with the route
        intersections = self.find_intersections(route, accident_polygons)
        return intersections

    def find_intersections(self, route: LineString, accident_polygons: list):
        """
        Finds accident polygons that intersect with the given route.

        Parameters:
        - route: A LineString object representing the route.
        - accident_polygons: A list of Polygon objects representing accident areas.

        Returns:
        - A GeoDataFrame of intersecting polygons.
        """
        # Create GeoDataFrame from accident polygons
        gdf_accidents = gpd.GeoDataFrame(
            {"geometry": accident_polygons}, crs="EPSG:4326"
        )

        # Simplify polygons for performance
        gdf_accidents["geometry"] = gdf_accidents["geometry"].simplify(tolerance=0.0001)

        # Create spatial index
        sindex_accidents = gdf_accidents.sindex

        # Find potential intersections using spatial index
        possible_matches_index = list(sindex_accidents.intersection(route.bounds))
        possible_matches = gdf_accidents.iloc[possible_matches_index]

        # Filter to find actual intersections
        intersections = possible_matches[possible_matches.intersects(route)]

        return intersections

    def create_buffered_polygons_for_intersections(
        self, intersections, buffer_distance_meters=10
    ):
        """
        Create buffered polygons for intersecting accident areas.

        Parameters:
        - intersections: GeoDataFrame of intersecting accident polygons.
        - buffer_distance_meters: Buffer distance in meters.

        Returns:
        - A list of buffered polygons in GeoJSON format.
        """
        buffered_polygons = []
        for _, row in intersections.iterrows():
            accident_polygon = row["geometry"]
            utm_zone = self.longitude_to_utm_zone(accident_polygon.centroid.x)

            # Define the CRS (Coordinate Reference System) for geographic coordinates (WGS84).
            geodetic = pyproj.CRS("EPSG:4326")
            # Define the CRS for the calculated UTM zone.
            utm = pyproj.CRS(f"EPSG:326{utm_zone}")

            # Create a transformer to convert from geodetic (latitude and longitude) to UTM coordinates.
            transformer_to_utm = pyproj.Transformer.from_crs(
                geodetic, utm, always_xy=True
            ).transform
            # Create a transformer to convert from UTM back to geodetic coordinates.
            transformer_to_geodetic = pyproj.Transformer.from_crs(
                utm, geodetic, always_xy=True
            ).transform

            # Transform the accident polygon's coordinates to UTM for accurate distance measurements.
            utm_polygon = transform(transformer_to_utm, accident_polygon)
            # Create a buffered polygon around the accident area with the specified buffer distance in meters.
            buffered_utm_polygon = utm_polygon.buffer(buffer_distance_meters)
            # Transform the buffered polygon's coordinates back to geodetic (latitude and longitude).
            buffered_polygon = transform(transformer_to_geodetic, buffered_utm_polygon)

            # Convert the buffered polygon to a GeoJSON-like Python dictionary.
            buffered_polygon_geojson = mapping(buffered_polygon)
            buffered_polygons.append(buffered_polygon_geojson["coordinates"])

        return buffered_polygons

    def longitude_to_utm_zone(self, longitude: int):
        """
        Determine the UTM zone for a given longitude.
        """
        return int((longitude + 180) / 6) + 1
