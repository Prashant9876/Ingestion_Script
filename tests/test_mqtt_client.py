import importlib
import json
import sys
import types
import unittest
from datetime import datetime, timezone


def _load_mqtt_module(allowed_farms):
    """Import src.mqtt_client with mocked Redis/Mongo modules."""
    sys.modules.pop("src.mqtt_client", None)
    sys.modules.pop("src.redis_client", None)
    sys.modules.pop("src.cosmos_dev", None)

    redis_calls = []
    mongo_calls = []
    config_calls = []
    lcd_revert_calls = []
    fan_revert_calls = []

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

    def check_and_update_device_config(payload, farm_id):
        config_calls.append({"payload": payload, "farm_id": farm_id})

    fake_redis.store_device_data = store_device_data
    fake_redis.load_allowed_farms = load_allowed_farms
    fake_redis.check_and_update_device_config = check_and_update_device_config

    fake_cosmos = types.ModuleType("src.cosmos_dev")

    def store_to_mongo(device_id, device_type, payload):
        mongo_calls.append(
            {"device_id": device_id, "device_type": device_type, "payload": payload}
        )
        return True

    fake_cosmos.store_to_mongo = store_to_mongo

    def revert_schedule_detail(payload, farm_id, mqtt_client):
        lcd_revert_calls.append(
            {"payload": payload, "farm_id": farm_id, "mqtt_client": mqtt_client}
        )
        return True

    def revert_Fan_schedule_detail(payload, farm_id, mqtt_client):
        fan_revert_calls.append(
            {"payload": payload, "farm_id": farm_id, "mqtt_client": mqtt_client}
        )
        return True

    fake_cosmos.revert_schedule_detail = revert_schedule_detail
    fake_cosmos.revert_Fan_schedule_detail = revert_Fan_schedule_detail

    sys.modules["src.redis_client"] = fake_redis
    sys.modules["src.cosmos_dev"] = fake_cosmos

    mqtt_module = importlib.import_module("src.mqtt_client")
    mqtt_module.config.ALLOWED_FARMS = allowed_farms
    return mqtt_module, redis_calls, mongo_calls, config_calls, lcd_revert_calls, fan_revert_calls


class _Msg:
    def __init__(self, topic, payload_dict):
        self.topic = topic
        self.payload = json.dumps(payload_dict).encode()


class _MqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class MqttClientTests(unittest.TestCase):
    def test_on_message_sensor_stores_to_redis_and_mongo(self):
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module(
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
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module(
            {"118": "Asia/Kolkata"}
        )
        msg = _Msg("farm/118/fertigation", {"Device_Id": "dev-2", "state": "on"})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(len(redis_calls), 1)
        self.assertEqual(redis_calls[0]["type"], "actuator")
        self.assertEqual(redis_calls[0]["payload"]["type"], "actuator")
        self.assertEqual(len(mongo_calls), 1)
        self.assertEqual(mongo_calls[0]["device_type"], "actuator")

    def test_sensor_preserves_device_timestamp(self):
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module(
            {"118": "Asia/Kolkata"}
        )
        payload = {
            "Device_Id": "dev-1",
            "timestamp": "2026-10-22T08:00:00Z",
            "Ist_timestamp": "2026-10-22T13:30:00+05:30",
        }
        msg = _Msg("farm/118/sensor", payload)

        mqtt_module.on_message(None, None, msg)

        stored_payload = redis_calls[0]["payload"]
        self.assertEqual(stored_payload["timestamp"], payload["timestamp"])
        self.assertEqual(stored_payload["Ist_timestamp"], payload["Ist_timestamp"])
        self.assertEqual(mongo_calls[0]["payload"]["timestamp"], payload["timestamp"])

    def test_actuator_preserves_device_timestamp(self):
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module(
            {"118": "Asia/Kolkata"}
        )
        payload = {
            "Device_Id": "dev-2",
            "timestamp": "2026-10-22T08:00:00Z",
        }
        msg = _Msg("farm/118/actuator", payload)

        mqtt_module.on_message(None, None, msg)

        stored_payload = redis_calls[0]["payload"]
        self.assertEqual(stored_payload["timestamp"], payload["timestamp"])
        self.assertNotIn("Ist_timestamp", stored_payload)
        self.assertEqual(mongo_calls[0]["payload"]["timestamp"], payload["timestamp"])

    def test_on_message_ignores_unallowed_farm(self):
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module({"999": "UTC"})
        msg = _Msg("farm/118/sensor", {"Device_Id": "dev-3", "temp": 30})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(redis_calls, [])
        self.assertEqual(mongo_calls, [])

    def test_on_message_ignores_invalid_topic(self):
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module({"118": "UTC"})
        msg = _Msg("farm/118", {"Device_Id": "dev-4"})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(redis_calls, [])
        self.assertEqual(mongo_calls, [])

    def test_sensor_keepalive_stores_once_in_mongo_with_ttl_datetime(self):
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module(
            {"118": "Asia/Kolkata"}
        )
        msg = _Msg("farm/118/sensor_keepalive", {"Device_Id": "sensor-1"})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(redis_calls, [])
        self.assertEqual(len(mongo_calls), 1)
        self.assertEqual(mongo_calls[0]["device_id"], "sensor-1")
        self.assertEqual(mongo_calls[0]["device_type"], "Keepalive")
        stored_payload = mongo_calls[0]["payload"]
        self.assertEqual(stored_payload["type"], "Keepalive")
        self.assertEqual(stored_payload["farm_id"], "118")
        self.assertIsInstance(stored_payload["createdAt"], datetime)
        self.assertEqual(stored_payload["createdAt"].tzinfo, timezone.utc)
        self.assertIn("Ist_timestamp", stored_payload)

    def test_actuator_keepalive_accepts_device_id_alias(self):
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module(
            {"118": "Asia/Kolkata"}
        )
        msg = _Msg("farm/118/actuator_keepalive", {"DeviceID": "actuator-1"})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(redis_calls, [])
        self.assertEqual(len(mongo_calls), 1)
        self.assertEqual(mongo_calls[0]["device_id"], "actuator-1")
        self.assertEqual(mongo_calls[0]["device_type"], "Keepalive")

    def test_keepalive_without_device_id_is_ignored(self):
        mqtt_module, redis_calls, mongo_calls, *_ = _load_mqtt_module(
            {"118": "Asia/Kolkata"}
        )
        msg = _Msg("farm/118/sensor_keepalive", {"status": "online"})

        mqtt_module.on_message(None, None, msg)

        self.assertEqual(redis_calls, [])
        self.assertEqual(mongo_calls, [])

    def test_info_fnc_reverts_fan_schedule(self):
        (
            mqtt_module,
            redis_calls,
            mongo_calls,
            config_calls,
            lcd_revert_calls,
            fan_revert_calls,
        ) = _load_mqtt_module({"211": "Australia/Perth"})
        client = _MqttClient()
        payload = {
            "DN": "FNC",
            "Device_id": "IFFNC2110000001",
            "rack_id": 1,
        }
        msg = _Msg("farm/211/Info", payload)

        mqtt_module.on_message(client, None, msg)

        self.assertEqual(len(config_calls), 1)
        self.assertEqual(config_calls[0]["farm_id"], "211")
        self.assertEqual(redis_calls, [])
        self.assertEqual(mongo_calls, [])
        self.assertEqual(lcd_revert_calls, [])
        self.assertEqual(len(fan_revert_calls), 1)
        self.assertEqual(fan_revert_calls[0]["payload"], payload)
        self.assertEqual(fan_revert_calls[0]["farm_id"], "211")
        self.assertIs(fan_revert_calls[0]["mqtt_client"], client)

    def test_info_afc_reverts_fan_schedule(self):
        (
            mqtt_module,
            redis_calls,
            mongo_calls,
            config_calls,
            lcd_revert_calls,
            fan_revert_calls,
        ) = _load_mqtt_module({"211": "Australia/Perth"})
        client = _MqttClient()
        payload = {
            "DN": "AFC",
            "Device_Id": "IFFNC2110000001",
            "rack_id": 1,
        }
        msg = _Msg("farm/211/Info", payload)

        mqtt_module.on_message(client, None, msg)

        self.assertEqual(len(config_calls), 1)
        self.assertEqual(redis_calls, [])
        self.assertEqual(mongo_calls, [])
        self.assertEqual(lcd_revert_calls, [])
        self.assertEqual(len(fan_revert_calls), 1)
        self.assertEqual(fan_revert_calls[0]["payload"], payload)
        self.assertEqual(fan_revert_calls[0]["farm_id"], "211")
        self.assertIs(fan_revert_calls[0]["mqtt_client"], client)

    def test_info_other_dn_only_updates_config(self):
        (
            mqtt_module,
            redis_calls,
            mongo_calls,
            config_calls,
            lcd_revert_calls,
            fan_revert_calls,
        ) = _load_mqtt_module({"211": "Australia/Perth"})
        client = _MqttClient()
        payload = {
            "DN": "IDC",
            "Device_Id": "IFIDC2110000001",
        }
        msg = _Msg("farm/211/Info", payload)

        mqtt_module.on_message(client, None, msg)

        self.assertEqual(len(config_calls), 1)
        self.assertEqual(config_calls[0]["payload"], payload)
        self.assertEqual(redis_calls, [])
        self.assertEqual(mongo_calls, [])
        self.assertEqual(lcd_revert_calls, [])
        self.assertEqual(fan_revert_calls, [])


if __name__ == "__main__":
    unittest.main()
