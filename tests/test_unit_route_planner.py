import unittest
from unittest.mock import patch, MagicMock
import os
from src.route_planner import RoutePlanner
from src.mqtt_client import MQTTClient
from src.accident_service import AccidentService


class TestRoutePlanner(unittest.TestCase):
    # lon, lat
    # From University of Oulu to Haukipudas
    global start_coords, end_coords
    start_coords = (25.466337, 65.059248)
    end_coords = (25.3523, 65.1765)

    @patch("src.accident_service.AccidentService")
    def setUp(self, mock_AccidentService):
        mock_get_accident_areas = MagicMock()
        mock_get_accident_areas.return_value = []

        # Assign this mock method to our mock AccidentService instance
        self.mock_accident_service_instance = mock_AccidentService.return_value
        self.mock_accident_service_instance.get_accident_areas = mock_get_accident_areas

        # Initialize RoutePlanner with the mocked AccidentService instance
        self.route_planner = RoutePlanner(self.mock_accident_service_instance)

    def test_get_basic_route(self):
        route = self.route_planner.get_route(start_coords, end_coords)

        self.assertIsNotNone(route, "The route should not be None")
        self.assertIn("features", route, "The route response should contain 'features'")
        self.assertTrue(
            len(route["features"]) > 0, "The route should contain at least one feature"
        )

    def test_get_basic_route_with_preference(self):
        preference = "fastest"

        route = self.route_planner.get_route(start_coords, end_coords, preference)

        self.assertIsNotNone(route, "The route should not be None")
        self.assertIn("features", route, "The route response should contain 'features'")
        self.assertTrue(
            len(route["features"]) > 0, "The route should contain at least one feature"
        )

    @patch("src.route_planner.RoutePlanner.get_accident_areas")
    def test_get_accidents_on_route(self, mock_get_accident_areas):
        accident_areas = [
            [  # on route
                (25.438747, 65.047514),
                (25.438747, 65.067514),
                (25.458747, 65.067514),
            ],
            [  # not on route
                (22.438747, 63.047514),
                (22.438747, 63.067514),
                (22.458747, 63.067514),
            ],
        ]

        intersections = self.route_planner.get_accidents_on_route(
            start_coords, end_coords, accident_areas
        )
        # there should be only 1 intersection since only 1 accident is on the desired route
        num_intersections = intersections.size
        self.assertEqual(num_intersections, 1)

        accident_areas = [
            # both on route
            [(25.438747, 65.047514), (25.438747, 65.067514), (25.458747, 65.067514)],
            [(25.438749, 65.047516), (25.438749, 65.067516), (25.458749, 65.067516)],
        ]

        intersections = self.route_planner.get_accidents_on_route(
            start_coords, end_coords, accident_areas
        )
        # there should be 2 intersections since both accidents are on route
        num_intersections = intersections.size
        self.assertEqual(num_intersections, 2)

    def test_route_with_and_without_avoid_area(self):
        # Mock the accident areas for the first route request
        self.route_planner.accident_areas = [
            [(25.438747, 65.047514), (25.438747, 65.067514), (25.458747, 65.067514)],
            [(25.438749, 65.047516), (25.438749, 65.067516), (25.458749, 65.067516)],
        ]

        regular_route = self.route_planner.get_route(start_coords, end_coords)
        self.assertIsNotNone(regular_route, "The route should not be None")
        self.assertIn(
            "features", regular_route, "The route response should contain 'features'"
        )
        self.assertTrue(
            len(regular_route["features"]) > 0,
            "The route should contain at least one feature",
        )

        # Mock empty accident areas for the second route request
        self.route_planner.accident_areas = []

        route_with_avoid_area = self.route_planner.get_route(start_coords, end_coords)
        self.assertIsNotNone(route_with_avoid_area, "The route should not be None")

        geometry_regular = regular_route["features"][0]["geometry"]["coordinates"]
        geometry_avoid = route_with_avoid_area["features"][0]["geometry"]["coordinates"]
        # The routes should be different since first route avoids accident areas
        assert (
            geometry_regular != geometry_avoid
        ), "The routes' geometries should be different."
