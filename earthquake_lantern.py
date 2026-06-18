# Rob Faludi 2025
# WiFi based on code from Rui Santos & Sara Santos
# https://randomnerdtutorials.com/raspberry-pi-pico-w-wi-fi-micropython/
# Flicker based on code from Grant Whitney
# https://grantwinney.com/raspberry-pi-flickering-candle/


import uasyncio as asyncio
from machine import Pin, PWM, reset, WDT
import time
import random
import _thread
import secrets
import gc
import ntptime
from nature_api import Client

version = "1.0.0"
print("Earthquake Lantern WiFi - Version:", version)

# Wi-Fi credentials
ssid = secrets.WIFI_SSID  # your SSID name
password = secrets.WIFI_PASSWORD  # your WiFi password

wdt = WDT(timeout=8388)  # 8-second watchdog timer

nature_client = Client(ssid, password, debug_mode=False, watchdog=wdt)

ipgeolocation_key = getattr(secrets, 'IPGEOLOCATION_API_KEY', None)
if ipgeolocation_key:
    try:
        nature_client.set_api_key('ipgeolocation', ipgeolocation_key)
    except Exception as e:
        print('Warning: failed to set ipgeolocation API key:', e)

red_pin = 5
green_pin = 6
blue_pin = 7

red_pin_2 = 8
green_pin_2 = 9
blue_pin_2 = 10
LED = Pin("LED", Pin.OUT)      # digital output for status LED

FETCH_INTERVAL = 60 * 60  # seconds
# MAGNITUDE_FACTOR_MULTIPLIER = 1.2
# MAGNITUDE_FACTOR_K = 0.03 # how strongly the wind factor is pulled towards the center value
# # A gentle breeze should have the most effect, and higher winds should have less effect to prevent the lantern from flickering too wildly in strong winds. 
# MAGNITUDE_FACTOR_CENTER = 6 # increase wind effect below this speed, decrease effect above this speed.

terminateThread = False

class Pulse(PWM):
    def duty(self, percent_duty):
        return self.duty_u16(int(percent_duty/100 *65535))
    
red_pwm = Pulse(Pin(red_pin))
red_pwm.freq(300)
red_pwm.duty(100)
green_pwm = Pulse(Pin(green_pin))
green_pwm.freq(300)
green_pwm.duty(100)
blue_pwm = Pulse(Pin(blue_pin))
blue_pwm.freq(300)
blue_pwm.duty(99)
red_pwm_2 = Pulse(Pin(red_pin_2))
red_pwm_2.freq(300)
red_pwm_2.duty(100)
green_pwm_2 = Pulse(Pin(green_pin_2))
green_pwm_2.freq(300)
green_pwm_2.duty(100)
blue_pwm_2 = Pulse(Pin(blue_pin_2))
blue_pwm_2.freq(300)
blue_pwm_2.duty(99)

def connect_to_wifi():
    wdt.feed()
    connection_success = nature_client.connect_wifi()
    return connection_success

def parse_datetime(timestamp):
    # Split the timestamp into date and time
    date_str, time_str = timestamp.split('T')
    # Extract year, month, day
    year, month, day = date_str.split('-')
    # Extract hours and minutes
    hour, minute = time_str.split(':')
    # Combine into final time format
    formatted_time = f"{month}/{day}/{year} {hour:2}:{minute:2} UTC"
    return(formatted_time)

# def fetch_weather_data():
#     try:
#         wdt.feed()
#         forecast = nature_client.get_forecast("current", "wind_speed_10m,wind_gusts_10m", forecast_days=1, expiry=300)
#         if not forecast or forecast.get('wind_speed_10m') is None:
#             return None
#         timestamp = f"{time.gmtime()[0]:04}-{time.gmtime()[1]:02}-{time.gmtime()[2]:02}T{time.gmtime()[3]:02}:{time.gmtime()[4]:02}"
#         return {
#             'current': {
#                 'wind_speed_10m': forecast.get('wind_speed_10m'),
#                 'wind_gusts_10m': forecast.get('wind_gusts_10m'),
#                 'time': timestamp
#             }
#         }
#     except Exception as e:
#         print('Error fetching weather data:', e)
#         return None
    
def fetch_earthquake_data(seconds=300):
    try:
        # --- EARTHQUAKES BY DATE RANGE ---
        print(f"Earthquakes in the past {seconds} seconds (all magnitudes):")
        now_ts = time.time()
        seconds_ago_ts = now_ts - seconds
        now_struct = time.gmtime(now_ts)
        prior_struct = time.gmtime(seconds_ago_ts)
        # Format YYYY-MM-DDTHH:MM:SS for USGS API
        today_str = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(now_struct[0], now_struct[1], now_struct[2], now_struct[3], now_struct[4], now_struct[5])
        seconds_ago_str = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(prior_struct[0], prior_struct[1], prior_struct[2], prior_struct[3], prior_struct[4], prior_struct[5])
        eq_params = {
            "starttime": seconds_ago_str,
            "endtime": today_str,
            "minmagnitude": 0,
            "orderby": "time",
            "limit": 1000  # set a high limit for data safety
        }
        wdt.feed()
        results = nature_client.get_earthquakes(eq_params)
        features = results.get("features", [])
        print(f"  Found: {len(features)} earthquakes in past {seconds // 60} minutes")
        return features
    except Exception as e:
        print('Error fetching earthquake data:', e)
        return None

async def watchdog_sleep(milliseconds):
    start_time = time.ticks_ms()
    while time.ticks_ms() - start_time < milliseconds:
        wdt.feed()
        await asyncio.sleep_ms(1000)
        
# class WindManager:
#     def __init__(self):
#         self.wind_factor = 0
#         self.speed = 0
#         self.start_time = time.ticks_ms()
#         self.delay = 0

#     def set_earthquake_data(self, wind_speed):
#         self.speed = wind_speed
#         self._calc_wind_factor(self.speed)

#     def adjust(self, x, k=0.02, center=10):
#         return x - k * (x - center) * abs(x - center)

#     def _calc_wind_factor(self, wind_speed):
#         self.wind_factor = max((wind_speed), 0) # protect against negative wind factor
#         # self.wind_factor = (self.wind_factor * WIND_FACTOR_MULTIPLIER)   # increase wind factor effect
#         self.wind_factor = self.adjust(self.wind_factor, k=0.02, center=10)

#     # def _calc_gusting(self):
#     #     if time.ticks_ms() - self.start_time > self.delay:
#     #         self.start_time = time.ticks_ms()
#     #         self.gust_ramp = random.randint(EVENT_LENGTH_LOW, GUST_LENGTH_HIGH) * 0.25
#     #         if not self.gusting:
#     #             self.gusting = True
#     #             self.gust_factor = self.gust_factor * random.uniform(0.8, 1.2) # add some randomness to gust factor
#     #             self.delay = random.randint(EVENT_LENGTH_LOW, GUST_LENGTH_HIGH)
#     #             # print("Gusting for", self.delay / 1000, "secs")
#     #         elif self.gusting:
#     #             self.gusting = False
#     #             self.delay = random.randint(EVENT_INTERVAL_LOW, GUST_INTERVAL_HIGH)
#     #             # print("Next gust in", self.delay / 1000, "secs") 
#     #     return self.wind_factor
    
#     def get_wind_factor(self):
#         factor = self.wind_factor * random.uniform(0.85, 1.0) # add some randomness
#         return factor
    
    
def red_light():
        global earthquake_manager
        factor = earthquake_manager.get_earthquake_factor()
        red_pwm.duty( 100 - min(random.uniform(93-factor, 100), 100) )
        red_pwm_2.duty(100 - min(random.uniform(93-factor, 100) , 100) ) 
        rand_flicker_sleep()
 
def green_light():
        global earthquake_manager
        factor = earthquake_manager.get_earthquake_factor()
        green_pwm.duty( 100 - min(random.uniform(33-factor, 34) ,100) )
        green_pwm_2.duty(100 - min(random.uniform(33-factor, 34) ,100) )
        rand_flicker_sleep()
 
def rand_flicker_sleep():
    time.sleep(random.randint(3, 10) / 100.0)

def light_candle():
    gc.collect()
    print("Starting candle thread")
    while terminateThread == False:
        red_light()
        green_light()
        time.sleep_ms(1)

class EarthquakeManager:
    def __init__(self):
        self.events = []
    
    def set_earthquake_data(self, event_time, magnitude):
        # event_time is in milliseconds (from USGS API)
        # Convert to seconds and add FETCH_INTERVAL to get start_time
        start_time = (event_time / 1000) + FETCH_INTERVAL
        duration_ms = self._calculate_duration(magnitude)
        self.events.append({
            'magnitude': magnitude,
            'event_time': event_time,
            'start_time': start_time,
            'duration_ms': duration_ms
        })
    
    def _calculate_duration(self, magnitude):
        # Duration in milliseconds: magnitude * 3
        return magnitude * 3 * 1000  # convert to milliseconds
    
    def _remove_expired_events(self):
        current_time = time.time()
        self.events = [e for e in self.events if e['start_time'] + (e['duration_ms'] / 1000) > current_time]
    
    def get_earthquake_factor(self):
        self._remove_expired_events()
        current_time = time.time()
        max_factor = 0
        
        for event in self.events:
            start_time = event['start_time']
            duration_sec = event['duration_ms'] / 1000  # convert to seconds
            end_time = start_time + duration_sec
            
            # Check if event is active (within start and end time)
            if start_time <= current_time <= end_time:
                elapsed = current_time - start_time
                remaining = duration_sec - elapsed
                percent_remaining = remaining / duration_sec if duration_sec > 0 else 0
                factor = event['magnitude'] * percent_remaining
                max_factor = max(max_factor, factor)
        
        return max_factor

earthquake_manager = EarthquakeManager()

async def main():
    wdt.feed()
    connection = connect_to_wifi()
    if not connection:
        print('Could not connect to Wi-Fi, exiting')
        reset()

    if not nature_client.sync_time():
        print('NTP sync failed, continuing with local time if available.')

    next_sync = time.time()
    while True:
        wdt.feed()
        if not nature_client.wifi_connected:
            break # exit if no connection
        if (time.time() >= next_sync):
            try:
                print('Syncing time via NTP...')
                wdt.feed()
                ntptime.settime()
                print(f"DateTime: {time.gmtime()[0]}-{time.gmtime()[1]:02}-{time.gmtime()[2]:02} {time.gmtime()[3]:02}:{time.gmtime()[4]:02}:{time.gmtime()[5]:02} UTC  ")
                next_sync = time.time() + 43200 # update every 12 hours
            except Exception as e:
                next_sync = time.time() + 600 # try again in 10 minutes
                print("Failed to update NTP, retrying in 10 minutes.", e)
        try:
            # Fetch and display earthquake data using nature_api
            earthquakes = fetch_earthquake_data(FETCH_INTERVAL) # get earthquakes in the past X seconds
            if earthquakes is not None and len(earthquakes) > 0:
                for eq in earthquakes:
                    properties = eq.get("properties", {})
                    magnitude = properties.get("mag", "N/A")
                    place = properties.get("place", "N/A")
                    event_time = properties.get("time", 0)
                    time_str = time.gmtime(event_time//1000)
                    time_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d} UTC".format(time_str[0], time_str[1], time_str[2], time_str[3], time_str[4])
                    print(f"  Magnitude {magnitude} earthquake at {place} on {time_str}")
                    earthquake_manager.set_earthquake_data(event_time, magnitude)
            else:
                print('No earthquake data available')
        except Exception as e:
            print('Error fetching earthquake data:', e)
        # show a list of all recorded earthquakes with their time, magnitude, start_time and duration
        print("Current earthquake events being tracked:")
        for event in earthquake_manager.events:
            print(f"  Magnitude {event['magnitude']} earthquake from {event['start_time']} replaying at {event['event_time']} with duration {event['duration_ms'] / 1000:.1f} seconds")  

        await watchdog_sleep(15*60*1000) # Read every 15 minutes

# Create an Event Loop
wdt = WDT(timeout=8388)  # 8-second watchdog timer
loop = asyncio.get_event_loop()
# Create a task to run the main function
loop.create_task(main())
_thread.start_new_thread(light_candle, ())

try:
    # Run the event loop indefinitely
    loop.run_forever()
except Exception as e:
    print('Error occurred: ', e)
except KeyboardInterrupt:
    red_pwm.duty(100)
    red_pwm_2.duty(100)
    green_pwm.duty(100)
    green_pwm_2.duty(100)
    print('Program Interrupted by the user')
    terminateThread = True

