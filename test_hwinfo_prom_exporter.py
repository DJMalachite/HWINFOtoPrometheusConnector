import importlib
import json
import math

import hwinfo_prom_exporter as exp


def test_parse_hwinfo_payload_still_works():
    payload = [
        {
            "SensorApp": "HWiNFO64",
            "SensorClass": "CPU [#0]",
            "SensorName": "Total CPU Usage",
            "SensorUnit": "%",
            "SensorUpdateTime": 123.4,
            "SensorValue": "51.2",
        }
    ]
    rows, raw = exp.parse_hwinfo_payload(payload)
    assert raw == 1
    assert len(rows) == 1
    assert rows[0]["sensor_unit"] == "percent"
    assert rows[0]["sensor_value"] == 51.2


def test_parse_mqtt_data_array_payload():
    payload = {
        "Topic": "aquasuite/AMPINEL",
        "Title": "MQTT Output",
        "Data": [
            {"Name": "Power", "Id": "data\\sensors\\0\\value", "Unit": "W", "Value": 59},
            {"Name": "Input voltage", "Id": "data\\voltages\\VoltageInAvg", "Unit": "V", "Value": 12.007},
        ],
    }
    rows, raw = exp.parse_mqtt_payload(payload, "aquasuite/AMPINEL", 1700000000.0)
    assert raw == 2
    assert len(rows) == 2
    assert rows[0]["source"] == "mqtt"
    assert rows[0]["sensor_unit"] == "watts"
    assert rows[1]["sensor_unit"] == "volts"


def test_bad_mqtt_json_increments_parse_error():
    class Msg:
        topic = "aquasuite/x"
        payload = b"{bad json"

    before = exp.state.mqtt_parse_errors_total
    exp.on_mqtt_message(None, None, Msg())
    assert exp.state.mqtt_parse_errors_total == before + 1


def test_stale_hide_mode_hides_values():
    exp.STALE_VALUE_MODE = "hide"
    now = exp.time.time()
    with exp.state.lock:
        exp.state.rows = [{
            "sensor_app": "a",
            "sensor_class": "b",
            "sensor_name": "n",
            "sensor_unit": "watts",
            "sensor_unit_raw": "W",
            "sensor_update_time": now,
            "sensor_value": 10.0,
            "occurrence": "1",
            "source": "mqtt",
        }]
        exp.state.source_up = 1
        exp.state.last_success_ts = now - (exp.DATA_FRESHNESS_TIMEOUT + 5)
    metrics = list(exp.HwinfoCollector().collect())
    names = {m.name for m in metrics}
    assert f"{exp.sanitize_name(exp.METRIC_PREFIX)}_sensor_value" not in names


def test_unit_normalization_variants():
    assert exp.normalize_unit("W") == "watts"
    assert exp.normalize_unit("A") == "amps"
    assert exp.normalize_unit("V") == "volts"
    assert exp.normalize_unit("%") == "percent"
    assert exp.normalize_unit("C") == "celsius"
    assert exp.normalize_unit("Â°C") == "celsius"
