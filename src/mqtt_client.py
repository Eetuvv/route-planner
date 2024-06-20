import os
import logging
import json
import paho.mqtt.client as mqtt
from src.route_planner import RoutePlanner
from src.accident_service import AccidentService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class MQTTClient:
    def __init__(self):
        self.hostname = os.getenv("MQTT_URL")
        self.port = int(os.getenv("MQTT_PORT"))
        self.request_topic = os.getenv("MQTT_REQUEST_TOPIC")
        self.response_topic = os.getenv("MQTT_RESPONSE_TOPIC")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.tls_set("isrgrootx1.crt")  # Use Let's Encrypt root CA
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish

        self.connect_to_broker()

        self.accident_service = AccidentService(self)
        self.route_planner = RoutePlanner(self.accident_service)

        self.accident_service.fetch_accident_data()
        self.accident_service.loop_start()

    def connect_to_broker(self):
        try:
            self.client.connect(self.hostname, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            logging.error(f"Failed to connect to MQTT broker: {e}")

    def on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            logging.info("Connected successfully to MQTT broker")
            client.subscribe(self.request_topic)
        else:
            logging.warning(f"Failed to connect, return code {rc}\n")

    def on_disconnect(self, client, userdata, flags, rc, properties):
        if rc != 0:
            logging.warning("Unexpected disconnection. Reconnecting...")
            client.reconnect()
        else:
            logging.info("Disconnected from MQTT broker")

    def on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        logging.info(f"Subscribed to topic {self.request_topic}")

    def on_publish(self, client, userdata, mid, rc, properties):
        logging.info(f"Message published to topic {self.response_topic}")

    def parse_request_message(self, msg: dict):
        data = json.loads(msg.payload.decode())
        start_coords = data["start"]
        end_coords = data["end"]
        route_params = {"start_coords": start_coords, "end_coords": end_coords}

        preference = data.get("preference")
        if preference is not None:
            route_params["preference"] = preference

        return route_params

    def on_message(self, client, userdata, msg):
        logging.info(f"Message received on topic {msg.topic}")
        # Assuming the message payload is a JSON string with "start" and "end" keys
        try:
            route_params = self.parse_request_message(msg)
            route = self.route_planner.get_route(**route_params)
            if route:
                logging.info("Route received succesfully.")
                self.publish_route(route)
            else:
                logging.error("Failed to fetch route.")
        except Exception as e:
            logging.error(f"Error processing message: {e}")

    def publish_route(self, route):
        try:
            self.client.publish(self.response_topic, json.dumps(route))
        except Exception as e:
            logging.error(f"Failed to publish message: {e}")
