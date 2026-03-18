import os
from dotenv import load_dotenv

load_dotenv()

# MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_ACK_TOPIC_PREFIX = os.getenv("MQTT_ACK_TOPIC_PREFIX")

# Redis
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX")
REDIS_FARMIDS_RSET_TIME = int(os.getenv("REDIS_FARMIDS_RSET_TIME", 30))  # seconds, how often to refresh allowed farm IDs from Redis

# Cosmos
# COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
# COSMOS_PRIMARY_KEY = os.getenv("COSMOS_PRIMARY_KEY")
# COSMOS_DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME")
# COSMOS_SENSOR_CONTAINER = os.getenv("COSMOS_SENSOR_CONTAINER")
# COSMOS_ACTUATOR_CONTAINER = os.getenv("COSMOS_ACTUATOR_CONTAINER")


# MongoDB
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DATABASE_NAME = os.getenv("MONGO_DATABASE_NAME")
MONGO_SENSOR_COLLECTION = os.getenv("MONGO_SENSOR_COLLECTION")
MONGO_ACTUATOR_COLLECTION = os.getenv("MONGO_ACTUATOR_COLLECTION")  

IOT_Device_Data_Database = os.getenv("IOT_Device_Data_Database")
IOT_Device_INFO_Database = os.getenv("IOT_Device_INFO_Database")
#timezone   

TIMEZONE_NAME = os.getenv("TIMEZONE", "UTC")  # default UTC



#Allowed farm_IDs
ALLOWED_FARMS = {}