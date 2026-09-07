# import os
# import time
# from azure.cosmos import CosmosClient, exceptions
# from src import config


# COSMOS_ENDPOINT = config.COSMOS_ENDPOINT
# COSMOS_PRIMARY_KEY = config.COSMOS_PRIMARY_KEY
# DATABASE_NAME = config.COSMOS_DATABASE_NAME

# SENSOR_CONTAINER_NAME = config.COSMOS_SENSOR_CONTAINER
# ACTUATOR_CONTAINER_NAME = config.COSMOS_ACTUATOR_CONTAINER

# if not all([COSMOS_ENDPOINT, COSMOS_PRIMARY_KEY, DATABASE_NAME]):
#     raise RuntimeError(" Cosmos ENV variables missing")

# cosmos_client = CosmosClient(
#     COSMOS_ENDPOINT,
#     credential=COSMOS_PRIMARY_KEY
# )

# database = cosmos_client.get_database_client(DATABASE_NAME)

# sensor_container = database.get_container_client(SENSOR_CONTAINER_NAME)
# actuator_container = database.get_container_client(ACTUATOR_CONTAINER_NAME)


# def store_to_cosmos(device_id: str, device_type:str ,payload: dict, retries: int = 3) -> bool:


#     try:
#         device_id = payload.get("Device_Id")

#         if not device_type or not device_id:
#             print("Missing type or Device_Id, skipping Cosmos")
#             return False

#         # Decide container
#         if device_type == "sensor":
#             container = sensor_container
#         elif device_type == "actuator":
#             container = actuator_container
#         else:
#             print(f"Unknown device type: {device_type}")
#             return False

#         payload["id"] = payload.get(
#             "Packet_Id",
#             f"{device_id}_{int(time.time())}"
#         )

#         payload["cosmos_ts"] = int(time.time())


#         for attempt in range(1, retries + 1):
#             try:
#                 result= container.upsert_item(payload)
#                 print(
#                     f"Cosmos stored | type={device_type} | id={payload['id']}"
#                 )
#                 print("Returned by upsert_item:", result)
#                 return True

#             except exceptions.CosmosHttpResponseError as e:
#                 print(
#                     f"Cosmos error (attempt {attempt}/{retries}): {e.message}"
#                 )
#                 time.sleep(2 ** attempt)

#         print("Cosmos write failed after retries")
#         return False

#     except Exception as e:
#         print(f"Unexpected Cosmos error: {e}")
#         return False



import time, json
from pymongo import MongoClient, errors
from src import config
import ast


# Mongo Config (add these in your config)
MONGO_URI = config.MONGO_URI
MONGO_DATABASE_NAME = config.MONGO_DATABASE_NAME

IOT_Device_Data_Database = config.IOT_Device_Data_Database
IOT_Device_INFO_Database = config.IOT_Device_INFO_Database
IOT_LCD_SCHEDULE_DATABASE = config.IOT_LCD_SCHEDULE_DATABASE

SENSOR_COLLECTION_NAME = config.MONGO_SENSOR_COLLECTION
ACTUATOR_COLLECTION_NAME = config.MONGO_ACTUATOR_COLLECTION
API_COLLECTION_NAME = config.MONGO_API_COLLECTION
KEEPALIVE_COLLECTION_NAME = config.MONGO_KEEPALIVE_COLLECTION
LCD_SCHEDULE_COLLECTION_NAME = config.LCD_SCHEDULE_COLLECTION_NAME
FAN_SCHEDULE_COLLECTION_NAME = config.FAN_SCHEDULE_COLLECTION_NAME


if not all([
    MONGO_URI,
    IOT_Device_Data_Database,
    IOT_Device_INFO_Database,
    IOT_LCD_SCHEDULE_DATABASE,
    SENSOR_COLLECTION_NAME,
    ACTUATOR_COLLECTION_NAME,
    API_COLLECTION_NAME,
    KEEPALIVE_COLLECTION_NAME,
    LCD_SCHEDULE_COLLECTION_NAME,
    FAN_SCHEDULE_COLLECTION_NAME,
]):
    raise RuntimeError("Mongo ENV variables missing")



mongo_client = MongoClient(MONGO_URI)
IoT_Device_database = mongo_client[IOT_Device_Data_Database]      # this db is for  storing sensor and actuator data in mongodb
IOT_Device_Info_database = mongo_client[IOT_Device_INFO_Database]   # this database is for storing device info in mongodb
IOT_LCD_Schedule_database_conn = mongo_client[IOT_LCD_SCHEDULE_DATABASE]  # this database is for storing LCD schedule data in mongodb


sensor_collection = IoT_Device_database[SENSOR_COLLECTION_NAME]         # sensor Collection
actuator_collection = IoT_Device_database[ACTUATOR_COLLECTION_NAME]        # actuator collection
apis_collection =IoT_Device_database[API_COLLECTION_NAME]             # API collection (using same as sensor for now)
keepalive_collection = IoT_Device_database[KEEPALIVE_COLLECTION_NAME]   # Keepalive collection
lcd_schedule_collection = IOT_LCD_Schedule_database_conn[LCD_SCHEDULE_COLLECTION_NAME]  # LCD Schedule collection
fan_schedule_collection = IOT_LCD_Schedule_database_conn[FAN_SCHEDULE_COLLECTION_NAME]  # Fan Schedule collection
# IoT_Device_Info_collection = IOT_Device_Info_database["Device_Info"]  # Collection for device info

keepalive_collection.create_index(
    "createdAt",
    expireAfterSeconds=3 * 24 * 60 * 60
)



def store_to_mongo(device_id: str, device_type: str, payload: dict, retries: int = 3) -> bool:
    try:
        # Accept the payload keys used by different producers without forcing a schema change.
        device_id = (
            payload.get("Device_Id")
            or payload.get("DeviceID")
            or payload.get("DeviceId")
        )

        if not device_type or not device_id:
            print("Missing type or device identifier, skipping Mongo")
            return False

        # Decide collection
        if device_type == "sensor":
            collection = sensor_collection
        elif device_type == "actuator":
            collection = actuator_collection
        elif device_type == "APIs":
            collection = apis_collection
        elif device_type == "Keepalive":
            collection = keepalive_collection
        else:
            print(f"Unknown device type: {device_type}")
            return False

        # Generate ID (similar to Cosmos logic)
        doc_id = payload.get(
            "Packet_Id",
            f"{device_id}_{int(time.time())}"
        )

        payload["_id"] = doc_id
        payload["mongo_ts"] = int(time.time())

        for attempt in range(1, retries + 1):
            try:
                # Upsert behavior
                result = collection.replace_one(
                    {"_id": doc_id},
                    payload,
                    upsert=True
                )

                print(f"Mongo stored | type={device_type} | id={doc_id}")
                print("Returned by replace_one:", result.raw_result)
                return True

            except errors.PyMongoError as e:
                print(f"Mongo error (attempt {attempt}/{retries}): {str(e)}")
                time.sleep(2 ** attempt)

        print("Mongo write failed after retries")
        return False

    except Exception as e:
        print(f"Unexpected Mongo error: {e}")
        return False


def updatemongo_config(Device_Id, farm_Id, mqtt_payload):
    global IOT_Device_INFO_Database
    try:
        print("🔍 Device_Id:", Device_Id, type(Device_Id))

        if not isinstance(Device_Id, str):
            print("❌ Invalid Device_Id")
            return

        data = mqtt_payload

        if not isinstance(data, dict):
            print("❌ Payload is not dict")
            return

        data["Device_Id"] = Device_Id

        print("🔎 FINAL DATA:", data)

        collection = IOT_Device_Info_database[str(farm_Id)]

        result = collection.update_one(
            {"Device_Id": Device_Id},
            {"$set": data},
            upsert=True
        )

        if result.matched_count > 0:
            print("🔄 Device updated in MongoDB")
        elif result.upserted_id:
            print("✅ New device inserted in MongoDB")

    except Exception as e:
        print("❌ Final Error:", e)


def revert_schedule_detail(payload, farm_id, mqtt_client):
    global IOT_Device_INFO_Database
    try:
        print("🔍 Reverting schedule detail for farm:", farm_id)
        rack_id = payload.get("rack_id")
        recieved_device_id = (
            payload.get("Device_Id")
            or payload.get("DeviceID")
            or payload.get("DeviceId")
            or payload.get("Device_id")
        )

        if rack_id is None:
            print("rack_id missing in payload")
            return None

        data = lcd_schedule_collection.find_one(
            {
                "farm_id": int(farm_id),
                "rack_id": int(rack_id)
            },
            {
                "_id": 0
            }
        )

        if data is None:
            print(
                f"No LCD schedule found for "
                f"farm_id={farm_id}, rack_id={rack_id}"
            )
            return None

        Stored_device_id = (
            data.get("device_ids")
            or data.get("Device_Id")
            or data.get("Device_ids")
            or []
        )
        stored_device_ids = {
            str(device_id).strip().rstrip(",")
            for device_id in Stored_device_id
        }
        valid_flag = str(recieved_device_id).strip().rstrip(",") in stored_device_ids
        if not valid_flag:
            print(
                f"Device_Id {recieved_device_id} not in stored Device_Id list: "
                f"{sorted(stored_device_ids)}"
            )
            return None

        mqtt_payload = {
            key: value
            for key, value in data.items()
            if key not in [
                "_id",
                "timezone",
                "last_updated_at",
                "device_ids",
            ]
        }

        # Optional command
        mqtt_payload["cmd"] = "newschedule"
        mqtt_payload["DeviceID"] = data.get("device_ids", [])

        print("MQTT Payload:")
        print(mqtt_payload)

        # Convert dictionary to JSON
        mqtt_message = json.dumps(mqtt_payload)
        mqtt_client.publish(
            f"farm/{farm_id}/SSub",
            mqtt_message
        )

        print("✅ Revert schedule sent to MQTT")

        return True
    except Exception as e:
        print("❌ Error occurred while reverting schedule detail:", e)



def revert_Fan_schedule_detail(payload, farm_id, mqtt_client):
    global IOT_Device_INFO_Database
    try:
        print("🔍 Reverting Fan schedule detail for farm:", farm_id)
        DN = payload.get("DN")
        recieved_device_id = (
            payload.get("Device_Id")
            or payload.get("DeviceID")
            or payload.get("DeviceId")
            or payload.get("Device_id")
        )



        data = fan_schedule_collection.find_one(
            {
                "farm_id": int(farm_id),
                "DN": str(DN).strip()

            },
            {
                "_id": 0
            }
        )

        if data is None:
            print(
                f"No Fan schedule found for "
                f"farm_id={farm_id}, DN={DN}"
            )
            return None

        Stored_device_id = (
            data.get("device_ids")
            or data.get("Device_Id")
            or data.get("Device_ids")
            or []
        )
        stored_device_ids = {
            str(device_id).strip().rstrip(",")
            for device_id in Stored_device_id
        }
        valid_flag = str(recieved_device_id).strip().rstrip(",") in stored_device_ids
        if not valid_flag:
            print(
                f"Device_Id {recieved_device_id} not in stored Device_Id list: "
                f"{sorted(stored_device_ids)}"
            )
            return None

        mqtt_payload = {
            key: value
            for key, value in data.items()
            if key not in [
                "_id",
                "timezone",
                "last_updated_at",
                "device_ids",
            ]
        }

        # Optional command
        mqtt_payload["cmd"] = "newschedule"
        mqtt_payload["DeviceID"] = data.get("device_ids", [])

        print("MQTT Payload:")
        print(mqtt_payload)

        # Convert dictionary to JSON
        mqtt_message = json.dumps(mqtt_payload)
        mqtt_client.publish(
            f"farm/{farm_id}/SSub",
            mqtt_message
        )

        print("✅ Revert Fan schedule sent to MQTT")

        return True
    except Exception as e:
        print("❌ Error occurred while reverting Fan schedule detail:", e)
