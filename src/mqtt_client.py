import json
import os
import time
import threading
import paho.mqtt.client as mqtt
from src import redis_client
from src import cosmos_dev
from datetime import datetime, timezone ,timedelta
from src import config
from zoneinfo import ZoneInfo 
import pytz 

IST_OFFSET = "Asia/Kolkata" # Indian Standard Time offset as this fsarm. is running in india 


# ========================
# ENV CONFIG
# ========================


MQTT_BROKER = config.MQTT_BROKER
MQTT_PORT = config.MQTT_PORT
MQTT_USERNAME = config.MQTT_USERNAME
MQTT_PASSWORD = config.MQTT_PASSWORD


MQTT_ACK_TOPIC_PREFIX = config.MQTT_ACK_TOPIC_PREFIX

PING_TOPIC = "farm/118/TimeSync"
PING_INTERVAL = 120  # seconds

TIMEZONE_NAME = config.TIMEZONE_NAME # default UTC

FARM_IDS_RELOAD_TIME = config.REDIS_FARMIDS_RSET_TIME  # seconds, how often to refresh allowed farm IDs from Redis  

last_refresh = 0

mqtt_client = None
connected = False

# ========================
# MQTT CALLBACKS
# ========================

def on_connect(client, userdata, flags, rc):
    global connected
    if rc == 0:
        connected = True
        print("MQTT connected")
        # Subscribe to all allowed farms
        if config.ALLOWED_FARMS:  # make sure it's not empty
            for farm_id in config.ALLOWED_FARMS.keys():  # iterate over dict keys (farm IDs)
                topic = f"farm/{farm_id}/#"
                client.subscribe(topic)
                print("Subscribed to:", topic)
        else:
            print("⚠️ ALLOWED_FARMS is empty. No subscriptions made.")
    else:
        print(" MQTT connection failed with code:", rc)

def on_disconnect(client, userdata, rc):
    global connected
    connected = False
    print("⚠ MQTT disconnected. Reconnecting...")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        print("\n▶ MQTT Topic:", msg.topic)
        print("▶ MQTT Payload:", payload)
        topic_parts = msg.topic.split("/")

        if len(topic_parts) < 3:
            print("Invalid topic format:", msg.topic)
            return
        
        farm_id = topic_parts[1]
        topic_type = topic_parts[2]

        if farm_id not in config.ALLOWED_FARMS:
            print(f"Farm {farm_id} not allowed")
            return
        
        device_id = payload.get("Device_Id")
    
        if topic_type == "sensor":
            payload["type"] = "sensor"
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            payload["farm_id"] = farm_id
        elif topic_type in {"actuator", "irrigation", "fertigation"}:
            payload["type"] = "actuator"
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            payload["farm_id"] = farm_id  # Example additional field for actuators
        # elif topic_type == "robot":
        #     payload["type"] = "robot"
        #     payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        #     payload["farm_id"] = farm_id  # Example additional field for robots
        else:
            print(f"Topic type {topic_type} not recognized")
            return
        
        redis_data = redis_client.store_device_data(device_id, payload, type=payload["type"], farm_Id=farm_id)
        cosmos_dev.store_to_mongo(device_id, payload["type"], payload)
    
    except Exception as e:
        print("Topic parsing error:", e)
    return
    

# ========================
# HEARTBEAT THREAD
# ========================

def heartbeat():
    global mqtt_client, last_refresh
    time.sleep(5)  # Initial delay to allow MQTT connection to establish
    while True:
        if connected and config.ALLOWED_FARMS:
            utc_now = datetime.utcnow().replace(tzinfo=pytz.UTC)

            for farm_id, tz_str in config.ALLOWED_FARMS.items():
                # Convert UTC to farm's local timezone using pytz
                farm_tz = pytz.timezone(tz_str)
                local_now = utc_now.astimezone(farm_tz)

                # IST time
                ist_now = utc_now.astimezone(pytz.timezone(IST_OFFSET))

                payload = {
                    "type": "heartbeat",
                    "farm_id": farm_id,
                    "utc_time": utc_now.isoformat().replace("+00:00", "Z"),
                    "ist_time": ist_now.isoformat(),
                    "local_time": local_now.isoformat(),
                    "epoch": int(time.time())
                }

                topic = f"farm/{farm_id}/heartbeat"
                mqtt_client.publish(topic, json.dumps(payload), qos=0)
                print(f"✅ Heartbeat sent to {topic} | Local Time: {local_now.isoformat()}")
                time.sleep(0.1)  # Small delay between heartbeats to different farms

        else:
            print("⚠️ No allowed farms or MQTT not connected. Heartbeat skipped.")
        
        now = time.time()
        if now - last_refresh >= FARM_IDS_RELOAD_TIME:
            try:
                redis_client.load_allowed_farms()
            except Exception as e:
                print("Error refreshing farms:", e)
            last_refresh = now
        
        time.sleep(PING_INTERVAL)

# ========================
# MQTT STARTER
# ========================

def start_mqtt():
    global mqtt_client, last_refresh

    redis_client.load_allowed_farms()  # Load allowed farms from Redis at startup
    time.sleep(2)  # Small delay to ensure Redis connection is established before MQTT starts
    last_refresh = time.time()  # Initialize last refresh time

    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    # Username & password
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Auto reconnect settings
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(" MQTT connection error:", e)
        raise SystemExit(1)

    # Start heartbeat thread
    
    threading.Thread(target=heartbeat, daemon=True).start() 

    print("🚀 MQTT client started with auto-reconnect & heartbeat")
    mqtt_client.loop_forever()
