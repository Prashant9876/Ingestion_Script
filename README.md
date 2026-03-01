# Ingestion_Script

MQTT ingestion service that:
- Subscribes to farm MQTT topics
- Validates farm IDs from Redis
- Stores recent payloads in Redis (last 30 per device/type)
- Upserts sensor/actuator payloads into MongoDB
- Publishes periodic heartbeat messages per farm timezone

## Project Structure

- `main.py`: entrypoint, starts MQTT loop.
- `src/config.py`: environment/config loading.
- `src/mqtt_client.py`: MQTT connect/subscribe/message handling + heartbeat thread.
- `src/redis_client.py`: Redis connection, allowed-farm refresh, Redis list writes.
- `src/cosmos_dev.py`: MongoDB persistence logic (`store_to_mongo`).

## Data Flow

1. Load allowed farms from Redis hash `IoT_Ingestion_script:{REDIS_KEY_PREFIX}`.
2. Connect to MQTT broker and subscribe to `farm/{farm_id}/#` for each allowed farm.
3. On message:
- Parse topic and payload.
- Validate farm ID.
- Normalize type (`sensor` / `actuator`) and add UTC timestamp.
- Push to Redis list `iothub:{farm_id}:{device_id}:{type}` (trim to last 30).
- Upsert same payload in Mongo collection (sensor/actuator).
4. Every 120 seconds, publish heartbeat to `farm/{farm_id}/heartbeat`.
5. Refresh allowed farms from Redis periodically (`REDIS_FARMIDS_RSET_TIME`, default `30s`).

## Requirements

- Python 3.9+
- Redis
- MQTT broker
- MongoDB

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create `.env` with:

```env
# MQTT
MQTT_BROKER=
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=
MQTT_ACK_TOPIC_PREFIX=

# Redis
REDIS_HOST=
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_KEY_PREFIX=
REDIS_FARMIDS_RSET_TIME=30

# Mongo
MONGO_URI=
MONGO_DATABASE_NAME=
MONGO_SENSOR_COLLECTION=
MONGO_ACTUATOR_COLLECTION=

# Timezone (default UTC)
TIMEZONE=UTC
```

## Run

```bash
python main.py
```

Expected startup log:
- Redis connected
- Allowed farms loaded
- MQTT connected and farm subscriptions created
- Heartbeat publishing started

## Notes

- Cosmos DB code is currently commented out; active persistence target is MongoDB.
- `Device_Id` is required in incoming payloads.
- Topic format expected: `farm/{farm_id}/{topic_type}` where `topic_type` is `sensor`, `actuator`, `irrigation`, or `fertigation`.
