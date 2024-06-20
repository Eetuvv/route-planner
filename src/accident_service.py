import os
import requests
import time
import threading


class AccidentService:
    def __init__(self, mqtt_client):
        self.mqtt_client = mqtt_client
        self.accident_areas = []
        self.new_accident = None
        self.api_url = os.getenv("MOCK_API_URL")
        self.api_key = os.getenv("MOCK_API_KEY")
        self.headers = {"API-KEY": self.api_key}

    def loop_start(self):
        thread = threading.Thread(target=self.fetch_new_accidents())
        thread.start()

    def fetch_accident_data(self, initial_fetch: bool = True):
        """
        Fetch accident data and process it.
        If initial_fetch = True, append all accidents from database to self.accident_areas
        else only append new accidents, and save the new accident to self.new_accident
        """
        data = self.get_data_from_api()
        if data:
            self.process_accident_data(data, initial_fetch)

    def fetch_new_accidents(self, initial_fetch: bool = False):
        """Periodically fetch and process new accident data."""
        while True:
            time.sleep(5)
            self.fetch_accident_data(initial_fetch)

    def get_data_from_api(self):
        """Fetch accident data from the API."""
        if not self.api_key:
            raise ValueError("MOCK_API_KEY is not set in the .env file.")
        response = requests.get(self.api_url, headers=self.headers)
        return response.json()

    def process_accident_data(self, data, initial_fetch: bool):
        """Process fetched data and update accident areas based on fetch type."""
        for obj in data:
            if "geometry" in obj and obj["geometry"]:
                accident_area = self.extract_accident_area(obj)

                # For initial fetch, append all accidents
                if initial_fetch:
                    self.accident_areas.append(accident_area)
                    continue

                # For subsequent fetches, only append new accidents
                if self.is_new_accident(accident_area):
                    self.accident_areas.append(accident_area)
                    self.new_accident = accident_area

    def extract_accident_area(self, accident_data: list):
        """Extract accident area coordinates from the data."""
        accident_areas = accident_data["geometry"][0]
        return [(point["longitude"], point["latitude"]) for point in accident_areas]

    def is_new_accident(self, accident_area: list):
        return accident_area not in self.accident_areas

    def get_accident_areas(self):
        return self.accident_areas

    def get_new_accident(self):
        return self.new_accident

    def clear_new_accident(self):
        self.new_accident = None

    def send_updated_route(self, route):
        self.mqtt_client.publish_route(route)
