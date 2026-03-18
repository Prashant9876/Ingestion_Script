import redis
import os
import time
import json
from src import config, cosmos_dev

REDIS_HOST = config.REDIS_HOST
REDIS_PORT = int(config.REDIS_PORT)
REDIS_USERNAME = getattr(config, "REDIS_USERNAME", "default")
REDIS_PASSWORD = config.REDIS_PASSWORD
REDIS_KEY_PREFIX = config.REDIS_KEY_PREFIX

try:
    # Non-TLS connection (your database is plain TCP)
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        health_check_interval=30
    )

    redis_client.ping()
    print("✅ Redis connected")

except Exception as e:
    print("❌ Redis connection failed:", e)
    raise SystemExit(1)

# def store_device_data(device_id, payload, type):

#     if not device_id:
#         raise ValueError("Device_Id missing")

#     redis_key = f"iothub:{REDIS_KEY_PREFIX}:{device_id}:{type}"

#     redis_client.set(redis_key, json.dumps(payload))

#     print("✅ Stored in Redis:", redis_key)

#     return payload

# import json


# def load_allowed_farms():

#     FARM_IDS_KEY  = f"IoT_Ingestion_script:{REDIS_KEY_PREFIX}"
#     farms = redis_client.smembers(FARM_IDS_KEY)
#     config.ALLOWED_FARMS = {farm for farm in farms}  # update global set
#     print(f"🔹 ALLOWED_FARMS updated: {config.ALLOWED_FARMS}")


def load_allowed_farms():
    FARM_IDS_KEY = f"IoT_Ingestion_script:{REDIS_KEY_PREFIX}"
    farms = redis_client.hgetall(FARM_IDS_KEY)
    # Update the global ALLOWED_FARMS dictionary
    config.ALLOWED_FARMS = farms
    
    print(f"🔹 ALLOWED_FARMS updated: {config.ALLOWED_FARMS}")



def store_device_data(device_id, payload, type,farm_Id):
    if not device_id:
        raise ValueError("Device_Id missing")

    redis_key = f"iothub:{farm_Id}:{device_id}:{type}"
    
    # Use pipeline to keep it atomic
    redis_client.pipeline() \
        .rpush(redis_key, json.dumps(payload)) \
        .ltrim(redis_key, -30, -1) \
        .execute()

    print("✅ Stored in Redis (last 30 only):", redis_key)

    return payload




def check_and_update_device_config(mqtt_payload, farm_Id: str):

    try:

        MAC_ID = mqtt_payload.get("MAC_ID")
        IP = mqtt_payload.get("IP")
        CHIP_No = mqtt_payload.get("CHIP_No")
        DN = mqtt_payload.get("DN")
        Device_Id = mqtt_payload.get("Device_Id")

          # can be dynamic if needed

        redis_key = f"Device_Config_Details:{farm_Id}:{Device_Id}"

        # Get existing JSON
        existing_data = redis_client.json().get(redis_key)

        if not existing_data:
            redis_client.json().set(redis_key, "$", {
                "MAC_ID": MAC_ID,
                "IP": IP,
                "CHIP_No": CHIP_No,
                "DN": DN
            })

            cosmos_dev.updatemongo_config(Device_Id, farm_Id, mqtt_payload)

            print("✅ New device config stored")
            return

    
        if ( existing_data.get("MAC_ID") == MAC_ID and
            existing_data.get("IP") == IP and
            existing_data.get("CHIP_No") == CHIP_No and
            existing_data.get("DN") == DN
        ):
            print("✅ No change detected")
            return

        # Update full JSON (simpler & faster)
        redis_client.json().set(redis_key, "$", {
            "MAC_ID": MAC_ID,
            "IP": IP,
            "CHIP_No": CHIP_No,
            "DN": DN
        })
        cosmos_dev.updatemongo_config(Device_Id, farm_Id, mqtt_payload)

        print("🔄 Device config updated")

    except Exception as e:
        print("❌ Error check_and_update_device_config:", e)
