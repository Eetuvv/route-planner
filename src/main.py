from dotenv import load_dotenv
from src.mqtt_client import MQTTClient

load_dotenv()


def main():
    mqtt_client = MQTTClient()

    try:
        while True:
            mqtt_client.client.loop_start()
    except KeyboardInterrupt:
        print("Program terminated by user.")
    finally:
        mqtt_client.client.disconnect()


if __name__ == "__main__":
    main()
