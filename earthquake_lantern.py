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
from nature_api import Client

version = "1.0.1"
print("Earthquake Lantern WiFi - Version:", version)

time.sleep(2) # allow usb connection on startup

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


demo_button = Pin(2, Pin.IN, Pin.PULL_UP)

red_pin = 5
green_pin = 6
blue_pin = 7

red_pin_2 = 8
green_pin_2 = 9
blue_pin_2 = 10
LED = Pin("LED", Pin.OUT)      # digital output for status LED

FETCH_INTERVAL = 5 * 60 * 1000 # milliseconds between earthquake data fetches
FACTOR_MULTIPLIER = 4.5 # multiplier to increase overall effect of earthquake factor on brightness

# Earthquake Generator Configuration
EQ_GEN_MIN_INTERVAL = 3000  # milliseconds (minimum time between generated earthquakes)
EQ_GEN_MAX_INTERVAL = 20000  # milliseconds (maximum time between generated earthquakes)
EQ_GEN_MIN_MAGNITUDE = 0.75 # minimum magnitude for generated earthquakes
EQ_GEN_MAX_MAGNITUDE = 2.5  # maximum magnitude for generated earthquakes
EQ_GEN_FUTURE_SECONDS = 5  # seconds in the future when generated earthquake occurs

terminateThread = False
last_button_press = 0

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

def format_time(timestamp):
    time_struct = time.gmtime(timestamp // 1000)  # Convert milliseconds to seconds
    formatted_time = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d} UTC".format(time_struct[0], time_struct[1], time_struct[2], time_struct[3], time_struct[4], time_struct[5])
    return formatted_time
    
def fetch_earthquake_data(seconds=300):
    try:
        # --- EARTHQUAKES BY DATE RANGE ---
        # print(f"Earthquakes in the past {seconds} seconds (all magnitudes):")
        now_ts = time.time()
        seconds_ago_ts = now_ts - seconds
        now_struct = time.gmtime(now_ts)
        prior_struct = time.gmtime(seconds_ago_ts)
        # Format YYYY-MM-DDTHH:MM:SS for USGS API
        today_str = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(now_struct[0], now_struct[1], now_struct[2], now_struct[3], now_struct[4], now_struct[5])
        seconds_ago_str = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(prior_struct[0], prior_struct[1], prior_struct[2], prior_struct[3], prior_struct[4], prior_struct[5])
        eq_params = {
            "updatedafter": seconds_ago_str,
            "minmagnitude": 0,
            "orderby": "time",
            "limit": 1000  # set a high limit for data safety
        }
        wdt.feed()
        results = nature_client.get_earthquakes(eq_params)
        features = results.get("features", [])
        # print(f"  Found: {len(features)} earthquakes in past {seconds // 60} minutes")
        return features
    except Exception as e:
        print('Error fetching earthquake data:', e)
        return None

async def watchdog_sleep(milliseconds):
    start_time = time.ticks_ms()
    while time.ticks_ms() - start_time < milliseconds:
        factor = earthquake_manager.get_earthquake_factor()
        count = len(earthquake_manager.events)
        elapsed_seconds = (time.ticks_ms() - start_time) // 1000
        spinner = '/' if elapsed_seconds % 2 == 0 else '\\'
        print(f" EQ Factor: {factor:.2f}, Active Events: {count}  {spinner}", end='   \r')
        wdt.feed()
        check_demo_button()
        await asyncio.sleep_ms(500)

def check_demo_button():
    global last_button_press
    if demo_button.value() == 0:  # if button is pressed
        if time.time() - last_button_press < 10:  # debounce for 10 seconds
            return
        print("Demo button pressed - generating simulated earthquake")
        magnitude = random.uniform(6, 7) # generate a strong earthquake for demo
        event_time = int((time.time() - (FETCH_INTERVAL // 1000) + EQ_GEN_FUTURE_SECONDS) * 1000)
        earthquake_manager.set_earthquake_data(event_time, magnitude, simulated=True)
        print(f"Generated simulated earthquake: Magnitude {magnitude:.2f} will play at {format_time(event_time + FETCH_INTERVAL)}")
        last_button_press = time.time()


def red_light():
        global earthquake_manager
        factor = earthquake_manager.get_earthquake_factor()
        red_pwm.duty( 100 - min(random.uniform(98-factor, 100), 100) )
        red_pwm_2.duty(100 - min(random.uniform(98-factor, 100) , 100) ) 
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
    
    def set_earthquake_data(self, event_time, magnitude, simulated=False):
        # event_time is in milliseconds (from USGS API)
        # Convert to seconds and add FETCH_INTERVAL to get start_time
        start_time = event_time + (FETCH_INTERVAL)
        duration_ms = self._calculate_duration(magnitude)
        self.events.append({
            'magnitude': magnitude,
            'event_time': event_time,
            'start_time': start_time,
            'duration_ms': duration_ms,
            'simulated': simulated
        })
    
    def _calculate_duration(self, magnitude):
        # Duration in milliseconds: magnitude * 3
        return int(magnitude * 3 * 1000)  # convert to milliseconds
    
    def _remove_expired_events(self):
        current_time = time.time()
        self.events = [e for e in self.events if e['start_time'] + e['duration_ms'] > current_time * 1000]  # convert current time to milliseconds
    
    def get_earthquake_factor(self):
        self._remove_expired_events()
        current_time = time.time()
        max_factor = 0
        
        for event in self.events:
            start_time = event['start_time']
            duration_ms = event['duration_ms']
            end_time = start_time + duration_ms
            
            # Check if event is active (within start and end time)
            if start_time <= ( current_time * 1000 ) <= end_time:
                # print("event is active ")
                elapsed = ( current_time * 1000 ) - start_time
                remaining = duration_ms - elapsed
                percent_remaining = remaining / duration_ms if duration_ms > 0 else 0
                factor = event['magnitude'] * percent_remaining
                max_factor = max(max_factor, factor)
        return max_factor * FACTOR_MULTIPLIER  # multiplier to increase overall effect

earthquake_manager = EarthquakeManager()

async def earthquake_generator():
    """Generate simulated earthquakes at random intervals."""
    while True:
        try:
            # Sleep for a random interval between min and max
            interval_ms = random.randint(EQ_GEN_MIN_INTERVAL, EQ_GEN_MAX_INTERVAL)
            await asyncio.sleep_ms(interval_ms)
            
            # Generate random magnitude
            magnitude = random.uniform(EQ_GEN_MIN_MAGNITUDE, EQ_GEN_MAX_MAGNITUDE)
            
            # Set event time to EQ_GEN_FUTURE_SECONDS in the future (in milliseconds)
            event_time = int((time.time() - (FETCH_INTERVAL // 1000) + EQ_GEN_FUTURE_SECONDS) * 1000)
            
            # Add the simulated earthquake
            earthquake_manager.set_earthquake_data(event_time, magnitude, simulated=True)
            print(f"Generated simulated earthquake: Magnitude {magnitude:.2f} will play at {format_time(event_time + FETCH_INTERVAL)}")
            
        except Exception as e:
            print(f"Error in earthquake generator: {e}")

async def main():
    wdt.feed()
    connection = connect_to_wifi()
    if not connection:
        print('Could not connect to Wi-Fi, exiting')
        reset()

    if not nature_client.sync_time():
        print('NTP sync failed, continuing with local time if available.')

    next_sync = time.time()
    next_fetch = time.time()
    while True:
        wdt.feed()
        gc.collect()
        if not nature_client.wifi_connected:
            break # exit if no connection
        if (time.time() >= next_sync):
            try:
                print('Syncing time via NTP...')
                wdt.feed()
                nature_client.sync_time()
                next_sync = time.time() + 43200 # update every 12 hours
            except Exception as e:
                next_sync = time.time() + 600 # try again in 10 minutes
                print("Failed to update NTP, retrying in 10 minutes.", e)
        if (time.time() >= next_fetch):
            try:
                # Fetch and display earthquake data using nature_api
                next_fetch = time.time() + (FETCH_INTERVAL // 1000) # schedule next fetch
                print(f"Current Time: {format_time(time.time() * 1000)}")
                earthquakes = fetch_earthquake_data(FETCH_INTERVAL // 1000) # get earthquakes in the past X seconds
                if earthquakes is not None and len(earthquakes) > 0:
                    print(f"Found: {len(earthquakes)} earthquakes in past {FETCH_INTERVAL // 60000} minutes")
                    for eq in earthquakes:
                        properties = eq.get("properties", {})
                        magnitude = properties.get("mag", "N/A")
                        place = properties.get("place", "N/A")
                        event_time = properties.get("updated", 0)
                        time_str = time.gmtime(event_time//1000)
                        time_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d} UTC".format(time_str[0], time_str[1], time_str[2], time_str[3], time_str[4], time_str[5])
                        print(f"  Magnitude {magnitude} earthquake at {place} on {format_time(event_time)}")
                        earthquake_manager.set_earthquake_data(event_time, magnitude, simulated=False)
                else:
                    print('  No new earthquake data available')
            except Exception as e:
                print('Error fetching earthquake data:', e)
       
            # show a list of all recorded earthquakes with their time, magnitude, start_time and duration
            if len(earthquake_manager.events) > 0:
                print("Current earthquake events being tracked:")
                for event in earthquake_manager.events:
                    source = "[SIMULATED]" if event['simulated'] else "[REAL]"
                    print(f"  {source} Magnitude {event['magnitude']} earthquake from {event['event_time']} replaying at {format_time(event['start_time'])} with duration {event['duration_ms'] / 1000:.1f} seconds")  
        await watchdog_sleep(2000) # sleep between fetches

# Create an Event Loop
wdt = WDT(timeout=8388)  # 8-second watchdog timer
loop = asyncio.get_event_loop()
# Create a task to run the main function
loop.create_task(main())
# Create a task to run the earthquake generator
loop.create_task(earthquake_generator())
_thread.start_new_thread(light_candle, ())

# print("Injecting initial earthquake data for testing...")
# earthquake_manager.set_earthquake_data(((time.time() * 1000) - (FETCH_INTERVAL - 20000)), 9.0, simulated=True)  # start 60 seconds after launch

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

