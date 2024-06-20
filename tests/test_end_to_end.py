import pytest
import os
import json
import time
import paho.mqtt.client as mqtt
from src.mqtt_client import MQTTClient

received_messages = []


@pytest.fixture(scope="session", autouse=True)
def check_openrouteservice_api_key():
    """Ensure OPENROUTESERVICE_API_KEY environment variable is set."""
    api_key = os.getenv("OPENROUTESERVICE_API_KEY")
    if api_key is None:
        raise EnvironmentError(
            "Environment variable OPENROUTESERVICE_API_KEY is not set but is required."
        )


@pytest.fixture(scope="session", autouse=True)
def setup_variables():
    """Set up env variables needed for MQTTClient and global variables for MQTT test clients"""
    # Default values for environment variables
    env_vars = {
        "MQTT_URL": "asd-mqtt-test.rahtiapp.fi",
        "MQTT_PORT": "443",
        "MQTT_REQUEST_TOPIC": "route/requests",
        "MQTT_RESPONSE_TOPIC": "route/responses",
    }

    for var, value in env_vars.items():
        os.environ[var] = value

    # Update global variables from environment variables
    global MQTT_URL, MQTT_PORT, MQTT_REQUEST_TOPIC, MQTT_RESPONSE_TOPIC
    MQTT_URL = os.getenv("MQTT_URL")
    MQTT_PORT = int(os.getenv("MQTT_PORT"))
    MQTT_REQUEST_TOPIC = os.getenv("MQTT_REQUEST_TOPIC")
    MQTT_RESPONSE_TOPIC = os.getenv("MQTT_RESPONSE_TOPIC")


@pytest.fixture(scope="module")
def mqtt_listener():
    """Test client to listen for messages on the response topic."""

    def on_message(client, userdata, msg):
        print(f"Message received: {msg.payload}")
        received_messages.append(json.loads(msg.payload.decode()))

    listener = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    listener.on_message = on_message
    listener.tls_set("isrgrootx1.crt")  # Use Let's Encrypt root CA
    listener.connect(MQTT_URL, MQTT_PORT, 60)
    listener.subscribe(MQTT_RESPONSE_TOPIC)
    listener.loop_start()


@pytest.fixture(scope="module")
def mqtt_message_sender():
    """Fixture to send messages over MQTT."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.tls_set("isrgrootx1.crt")  # Use Let's Encrypt root CA
    client.connect(MQTT_URL, MQTT_PORT, 60)

    def publish(topic, message):
        """Function to publish a message to a given topic."""
        client.publish(topic, json.dumps(message))

    yield publish


@pytest.fixture(scope="function")
def mocked_accident_service(mocker):
    """Mock the AccidentService and its get_accident_areas method."""
    # Mock the AccidentService class
    mock_accident_service_cls = mocker.patch("src.mqtt_client.AccidentService")
    # Setup the mock to return a predefined value for get_accident_areas
    mock_accident_service_cls.return_value.get_accident_areas.return_value = []
    return mock_accident_service_cls.return_value


@pytest.fixture(scope="function")
def mqtt_client(mocked_accident_service):
    """Provide a MQTTClient instance with mocked dependencies."""
    # Initialize MQTTClient with mocked AccidentService
    client = MQTTClient()
    return client


def test_end_to_end(mqtt_message_sender, mqtt_listener, mqtt_client):
    """
    Test requesting and receiving routes over MQTT.

    This test does the following:
    - Custom mqtt_message_sender publishes a route request to route/requests topic.
    - MQTTClient then processes the request, fetches route from OpenRouteService, and
      sends the route object to route/responses.
    - Custom mqtt_listener checks that route is on route/responses topic,
      and that the route is valid.
    """
    mqtt_client.client.loop_start()

    # sleep 1 second to ensure listener has connected
    time.sleep(1)

    message = {
        "start": [25.466337, 65.059248],
        "end": [25.3523, 65.1765],
        "preference": "fastest",
    }
    # send route request message through fixture
    mqtt_message_sender(MQTT_REQUEST_TOPIC, message)

    # sleep 2 seconds to ensure messages have been received
    time.sleep(2)

    assert received_messages, "No response received."

    route = received_messages[0]
    assert route is not None, "The route should not be None"
    assert "features" in route, "The route response should contain 'features'"
    assert len(route["features"]) > 0, "The route should contain at least one feature"
