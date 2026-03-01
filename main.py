from dotenv import load_dotenv
from src.mqtt_client import start_mqtt
from src.redis_client import redis_client
from src.cosmos_dev import store_to_mongo


if __name__ == "__main__":
    print("🚀 MQTT → Redis → Cosmos service starting")
    start_mqtt()
#

