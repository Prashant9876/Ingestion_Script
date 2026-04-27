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

SENSOR_COLLECTION_NAME = config.MONGO_SENSOR_COLLECTION
ACTUATOR_COLLECTION_NAME = config.MONGO_ACTUATOR_COLLECTION
API_COLLECTION_NAME = config.MONGO_API_COLLECTION

if not all([MONGO_URI, IOT_Device_Data_Database, IOT_Device_INFO_Database , SENSOR_COLLECTION_NAME, ACTUATOR_COLLECTION_NAME]):
    raise RuntimeError("Mongo ENV variables missing")



mongo_client = MongoClient(MONGO_URI)
IoT_Device_database = mongo_client[IOT_Device_Data_Database]      # this db is for  storing sensor and actuator data in mongodb
IOT_Device_Info_database = mongo_client[IOT_Device_INFO_Database]   # this database is for storing device info in mongodb


sensor_collection = IoT_Device_database[SENSOR_COLLECTION_NAME]         # sensor Collection
actuator_collection = IoT_Device_database[ACTUATOR_COLLECTION_NAME]        # actuator collection
apis_collection =IoT_Device_database[API_COLLECTION_NAME]             # API collection (using same as sensor for now)

# IoT_Device_Info_collection = IOT_Device_Info_database["Device_Info"]  # Collection for device info      





def store_to_mongo(device_id: str, device_type: str, payload: dict, retries: int = 3) -> bool:
    try:
        device_id = payload.get("Device_Id")

        if not device_type or not device_id:
            print("Missing type or Device_Id, skipping Mongo")
            return False

        # Decide collection
        if device_type == "sensor":
            collection = sensor_collection
        elif device_type == "actuator":
            collection = actuator_collection
        elif device_type == "APIs":
            collection = apis_collection
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