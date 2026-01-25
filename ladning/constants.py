import datetime as dt

MILES_TO_KILOMETERS = 1.609344
BATTERY_CAPACITY_KWH = 57.5  # Tesla Model 3 Highland RWD
CHARGING_KW_MAX = 10.6  # Observed Easee Lite realistic charging speed until 95%+ SoC
CHARGING_KW_END = 7.6  # Observed Easee Lite realistic charging speed after 95%+ SoC
APPROX_MAX_RANGE_KM = 450  # Realistic Tesla Model 3 Highland RWD range on highways

SAMPLING_PERIOD = dt.timedelta(minutes=15)  # Everything happens in quarter-hour windows
PRICE_FRACTION_OF_HOUR = 0.25  # The fraction of an hour covered by each price entry
