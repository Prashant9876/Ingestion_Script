import importlib
import json
import sys
import types
import unittest


def _load_mqtt_module(allowed_farms):
    """Import src.mqtt_client with mocked Redis/Mongo modules."""
    sys.modules.pop("src.mqtt_client", None)
    sys.modules.pop("src.redis_client", None)
    sys.modules.pop("src.cosmos_dev", None)

    redis_calls = []
    mongo_calls = []

    fake_redis = types.ModuleType("src.redis_client")

    def store_device_data(device_id, payload, type, farm_Id):
        redis_calls.append(
            {
                "device_id": device_id,
                "payload": payload,
                "type": type,
                "farm_Id": farm_Id,
            }
        )
        return payload

    def load_allowed_farms():
        return None

    fake_redis.store_device_data = store_device_data
    fake_redis.load_allowed_farms = load_allowed_farms

    fake_cosmos = types.ModuleType("src.cosmos_dev")

    def store_to_mongo(device_id, device_type, payload):
        mongo_calls.append(
            {"device_id": device_id, "device_type": device_type, "payload": payload}
        )
        return True

    fake_cosmos.store_to_mongo = store_to_mongo

    sys.modules["src.redis_client"] = fake_redis
    sys.modules["src.cosmos_dev"] = fake_cosmos

    mqtt_module = importlib.import_module("src.mqtt_client")
    mqtt_module.config.ALLOWED_FARMS = allowed_farms
    return mqtt_module, redis_calls, mongo_calls


class _Msg:
    def __init__(self, topic, payload_dict):
        self.topic = topic
        self.payload = json.dumps(payload_dict).encode()


class MqttClientTests(unittest.TestCase):
    def test_on_message_sensor_stores_to_redis_and_mongo(self):
        mqtt_module, redis_calls, mongo_calls = _load_mqtt_module(
            {"118": "Asia/Kolkata"}
        )
        msg = _Msg("farm/118/sensor", {"Device_Id": "dev-1", "temp": 27})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(len(redis_calls), 1)
        self.assertEqual(len(mongo_calls), 1)
        self.assertEqual(redis_calls[0]["device_id"], "dev-1")
        self.assertEqual(redis_calls[0]["farm_Id"], "118")
        self.assertEqual(redis_calls[0]["type"], "sensor")
        self.assertEqual(redis_calls[0]["payload"]["type"], "sensor")
        self.assertEqual(redis_calls[0]["payload"]["farm_id"], "118")
        self.assertIn("timestamp", redis_calls[0]["payload"])
        self.assertEqual(mongo_calls[0]["device_type"], "sensor")

    def test_on_message_fertigation_maps_to_actuator(self):
        mqtt_module, redis_calls, mongo_calls = _load_mqtt_module(
            {"118": "Asia/Kolkata"}
        )
        msg = _Msg("farm/118/fertigation", {"Device_Id": "dev-2", "state": "on"})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(len(redis_calls), 1)
        self.assertEqual(redis_calls[0]["type"], "actuator")
        self.assertEqual(redis_calls[0]["payload"]["type"], "actuator")
        self.assertEqual(len(mongo_calls), 1)
        self.assertEqual(mongo_calls[0]["device_type"], "actuator")

    def test_on_message_ignores_unallowed_farm(self):
        mqtt_module, redis_calls, mongo_calls = _load_mqtt_module({"999": "UTC"})
        msg = _Msg("farm/118/sensor", {"Device_Id": "dev-3", "temp": 30})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(redis_calls, [])
        self.assertEqual(mongo_calls, [])

    def test_on_message_ignores_invalid_topic(self):
        mqtt_module, redis_calls, mongo_calls = _load_mqtt_module({"118": "UTC"})
        msg = _Msg("farm/118", {"Device_Id": "dev-4"})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(redis_calls, [])
        self.assertEqual(mongo_calls, [])


if __name__ == "__main__":
    unittest.main()
