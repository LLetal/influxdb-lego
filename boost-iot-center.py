import asyncio
import datetime
import random
from time import sleep

from bleak import BleakScanner
from influxdb_client import Point
from paho.mqtt import client as mqtt_client
from pylgbst import logging, get_connection_bleak
from pylgbst.hub import MoveHub
from pylgbst.peripherals import EncodedMotor, TiltSensor

# MQTT settings
broker = "0.0.0.0"
port = 1883
topic = "iot_center"


def connect_mqtt():
    def on_connect(rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client2 = mqtt_client.Client()
    client2.on_connect = on_connect
    client2.connect(broker, port)
    return client2


def data_send(metric_name, data):
    p = Point("environment") \
        .tag("CO2Sensor", "virtual_CO2Sensor") \
        .tag("PressureSensor", "virtual_PressureSensor") \
        .tag("HumiditySensor", "virtual_HumiditySensor") \
        .tag("TVOCSensor", "virtual_TVOCSensor") \
        .tag("clientId", "lego_boost") \
        .field(metric_name, float(data)) \
        .time(datetime.datetime.utcnow())
    logging.info("> " + p.to_line_protocol())
    client_mqtt.publish(topic, p.to_line_protocol())


async def auto_search():
    logging.basicConfig(level=logging.INFO, format='%(relativeCreated)d\t%(levelname)s\t%(name)s\t%(message)s')
    logging.info("Searching for Lego Hub...")
    devices = await BleakScanner.discover(timeout=10)
    possible_devices = []
    for d in devices:
        if d.name == "Move Hub":
            possible_devices.append(d)

    if len(str(possible_devices[1].metadata)) > len(str(possible_devices[0].metadata)):
        return possible_devices[1].name, possible_devices[1].address
    else:
        return possible_devices[0].name, possible_devices[0].address


def led_random(mhub):
    for x in range(20):
        mhub.led.set_color(random.randrange(0, 10))


def run(mhub):
    def callback_a(speed):
        data_send("TVOC", speed)

    def callback_b(speed):
        data_send("TVOC", speed)

    def rgb_callback(values):
        data_send("rgb", values)

    def axis_callback(x, y, z):
        data_send("Pressure", x)
        data_send("Temperature", y)
        data_send("Humidity", z)

    def battery_callback(values):
        data_send("CO2", values)

    mhub.motor_A.subscribe(callback_a, mode=EncodedMotor.SENSOR_ANGLE)
    mhub.motor_B.subscribe(callback_b, mode=EncodedMotor.SENSOR_ANGLE)
    mhub.led.subscribe(rgb_callback)
    mhub.tilt_sensor.subscribe(axis_callback, mode=TiltSensor.MODE_3AXIS_ACCEL)
    mhub.voltage.subscribe(battery_callback)

    while True:
        try:
            sleep(0.3)
        except KeyboardInterrupt:
            break

    mhub.led.unsubscribe(rgb_callback)
    mhub.tilt_sensor.unsubscribe(axis_callback)
    mhub.voltage.unsubscribe(battery_callback)
    mhub.motor_B.unsubscribe(callback_b)
    mhub.motor_A.unsubscribe(callback_a)


name, UUID = asyncio.run(auto_search())

if __name__ == '__main__':
    parameters = {}
    hub = None
    try:
        client_mqtt = connect_mqtt()
        logging.info("Connecting to Lego Hub...")
        connection = get_connection_bleak(hub_mac=str(UUID), hub_name=str(name))
        parameters['connection'] = connection
        hub = MoveHub(**parameters)
        logging.info("Running Demo...")
        run(hub)
    except Exception as e:
        print(e)
    finally:
        if hub is not None:
            hub.disconnect()
