import unittest
from unittest.mock import patch, MagicMock
import os
import json
from src.mqtt_client import MQTTClient
import paho.mqtt.client as mqtt


class TestMQTTClientCallbacks(unittest.TestCase):

    def setUp(self):
        # Patch the MQTT client to prevent actual network operations
        patcher_mqtt = patch("paho.mqtt.client.Client")
        self.MockMQTTClient = patcher_mqtt.start()
        self.addCleanup(patcher_mqtt.stop)

        # Mock environment variables required for MQTTClient
        os.environ["MQTT_URL"] = "test-url.com"
        os.environ["MQTT_PORT"] = "443"
        os.environ["MQTT_REQUEST_TOPIC"] = "request/topic"
        os.environ["MQTT_RESPONSE_TOPIC"] = "response/topic"

        # Patch and mock AccidentService used by MQTTClient
        self.accident_service_patch = patch("src.mqtt_client.AccidentService")
        self.mock_accident_service = self.accident_service_patch.start()
        # Configure the mock AccidentService instance as needed, for example:
        self.mock_accident_service_instance = self.mock_accident_service.return_value
        self.addCleanup(self.accident_service_patch.stop)

        # Mock RoutePlanner to prevent actual API calls
        self.route_planner_patch = patch("src.mqtt_client.RoutePlanner")
        self.mock_route_planner = self.route_planner_patch.start()
        self.mock_route_planner_instance = self.mock_route_planner.return_value
        self.mock_route_planner_instance.get_route.return_value = {"features": []}
        self.addCleanup(self.route_planner_patch.stop)

        # Initialize MQTTClient which now uses the mocked MQTT client and AccidentService
        self.mqtt_client = MQTTClient()

    def test_on_connect_success(self):
        """Test on_connect with a successful connection logs appropriate message."""
        with self.assertLogs(level="INFO") as log:
            self.mqtt_client.on_connect(self.mqtt_client.client, None, {}, 0, None)
            self.assertIn("Connected successfully to MQTT broker", log.output[0])

    def test_on_disconnect_unexpected(self):
        """Test on_disconnect logs a warning on unexpected disconnection."""
        with self.assertLogs(level="WARNING") as log:
            self.mqtt_client.on_disconnect(
                self.mqtt_client.client, None, {}, rc=1, properties=None
            )
            self.assertIn("Unexpected disconnection. Reconnecting...", log.output[0])

    def test_on_disconnect_expected(self):
        """Test on_disconnect logs info on expected disconnection."""
        with self.assertLogs(level="INFO") as log:
            self.mqtt_client.on_disconnect(
                self.mqtt_client.client, None, {}, rc=0, properties=None
            )
            self.assertIn("Disconnected from MQTT broker", log.output[0])

    def test_on_subscribe(self):
        """Test on_subscribe logs the correct message."""
        with self.assertLogs(level="INFO") as log:
            self.mqtt_client.on_subscribe(
                self.mqtt_client.client,
                None,
                123,
                [0],
                None,
            )
            expected_message = f"Subscribed to topic {os.environ['MQTT_REQUEST_TOPIC']}"
            self.assertTrue(any(expected_message in log_msg for log_msg in log.output))

    def test_on_message(self):
        """Test on_message logs receiving a message."""
        fake_msg = MagicMock(
            topic=self.mqtt_client.request_topic,
            payload=json.dumps({"start": [0, 0], "end": [1, 1]}).encode(),
        )
        with self.assertLogs(level="INFO") as log:
            self.mqtt_client.on_message(self.mqtt_client.client, None, fake_msg)
            self.assertIn("Message received on topic request/topic", log.output[0])

    def test_on_publish(self):
        """Test on_publish logs message publication success."""
        with self.assertLogs(level="INFO") as captured_logs:
            self.mqtt_client.on_publish(None, None, mid=123, rc=0, properties=None)
            self.assertIn(
                f"Message published to topic {os.environ['MQTT_RESPONSE_TOPIC']}",
                captured_logs.output[0],
            )
