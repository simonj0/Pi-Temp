#!/usr/bin/env python
import sqlite3
import sys
import Adafruit_DHT
def log_values(conn, sensor_id, temp, hum):
    curs = conn.cursor()
    curs.execute("CREATE TABLE IF NOT EXISTS sensor_values (rDatetime datetime, sensorID text, temperature numeric, humidity numeric)")
    curs.execute("INSERT INTO sensor_values values(datetime('now', 'localtime'), (?), (?), (?))", (sensor_id, temp, hum))
    conn.commit()
    conn.close()

def check_values(conn, temperature, humidity):
    if temperature is None or humidity is None:
        return False
    if humidity > 100 or humidity < 0:
        return False
    if temperature > 100 or temperature < -50:
        return False
    try:
        curs = conn.cursor()
        # get last value from within the past 8 minutes
        curs.execute("SELECT * FROM sensor_values WHERE rDatetime > datetime('now', '-8 minutes', 'localtime') ORDER BY 1 DESC LIMIT 1")
        value = curs.fetchone()
        if value is not None:
            prev_temperature = value[2]
            prev_humidity = value[3]
            if abs(temperature - prev_temperature) > max(2, prev_temperature*0.1) or abs(humidity - prev_humidity) > max(2, prev_humidity*0.1):
                return False
    except:
        pass

    return True
    

conn = sqlite3.connect('./pi-temp.db')
humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, 17)
if check_values(conn, temperature, humidity):
    log_values(conn, '1', temperature, humidity)
