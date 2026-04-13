# pyiq4

Async Python client for the Rain Bird IQ4 cloud API.

Rain Bird's 2.0 firmware moved all schedule management to the IQ4 cloud. The local controller API no longer returns schedule data on firmware 4.98+. This library talks directly to the IQ4 cloud API, giving full read/write access to irrigation programs, stations, runtimes, and start times.

## Disclaimer

This project is not affiliated with, endorsed by, or supported by Rain Bird Corporation. Use at your own risk.

## Credits

This library is a Python port of [rainbird-iq4-cli](https://github.com/nickustinov/rainbird-iq4-cli) by [@nickustinov](https://github.com/nickustinov), which is the original open-source implementation of the IQ4 cloud API.

## Installation

```bash
pip install pyiq4
```

Or with uv:

```bash
uv add pyiq4
```

Requires Python 3.12+. The only runtime dependency is `aiohttp`.

## Quick start

```python
import asyncio
import aiohttp
from pyiq4 import authenticate, RainbirdIQ4Client

async def main():
    async with aiohttp.ClientSession() as session:
        token = await authenticate(session, "you@example.com", "password")
        client = RainbirdIQ4Client(session, token)

        controllers = await client.get_controllers()
        for c in controllers:
            programs = await client.get_programs(c.id)
            for p in programs:
                print(f"{c.name} / {p.name}  adjust={p.seasonal_adjustment}%")

asyncio.run(main())
```

## API

### Authentication

```python
token = await authenticate(session, username, password)
```

Performs the OIDC implicit flow against Rain Bird's identity server. Returns a JWT token (~2 hour lifetime). Store it and pass it to `RainbirdIQ4Client`; re-authenticate when you get a `RainbirdAuthError`.

### Client

```python
client = RainbirdIQ4Client(session, token)
client.update_token(new_token)  # replace token after re-auth
```

#### Read operations

```python
await client.get_sites()
await client.get_controllers()
await client.get_connection_status(controller_ids)   # real-time MQTT status
await client.get_programs(controller_id)
await client.get_program_detail(program_id)          # full object for writes
await client.get_start_times(controller_id)
await client.get_stations(controller_id)
await client.get_station_runtimes(controller_id)
await client.get_program_step(step_id)               # full object for writes
```

#### Write operations

```python
# Seasonal adjustment / water days
detail = await client.get_program_detail(program_id)
detail.seasonal_adjustment = 130
detail.week_days = format_weekdays(["Mo", "We", "Fr"])
await client.update_program(detail)

# Station runtime
from dataclasses import replace
step = await client.get_program_step(step_id)
await client.update_program_step(replace(step, run_time_ticks=minutes_to_ticks(15)))

# Start times
await client.add_start_time(program_id, "06:00")
await client.delete_start_times(program_id, [start_time_id])

# Program steps (station assignments)
from pyiq4 import NewProgramStep
await client.add_program_steps([NewProgramStep(program_id=p_id, station_id=s_id)])
await client.delete_program_steps([step_id])
```

### Utilities

```python
from pyiq4 import (
    minutes_to_ticks, ticks_to_minutes,   # runtime conversion
    parse_weekdays, format_weekdays,       # "MoWeFr" <-> "0101010"
    parse_timespan, format_timespan,       # "00:10:00" <-> ticks
)
```

### Exceptions

```python
from pyiq4 import RainbirdAuthError, RainbirdAPIError, RainbirdConnectionError

try:
    token = await authenticate(session, username, password)
except RainbirdAuthError:
    # Bad credentials, token expired, or AWS WAF block
    ...
except RainbirdConnectionError:
    # Network failure
    ...
except RainbirdAPIError as e:
    # Non-2xx API response
    print(e.status_code, e.response_body)
```

## Data model

```
Account → Sites → Controllers (Satellites)
                    ├── Stations  (physical valve zones)
                    └── Programs  (A / B / C irrigation schedules)
                        ├── Start times  (when to run)
                        ├── Program steps  (station → runtime mapping)
                        └── Seasonal adjustment  (% scaling of all runtimes)
```

## License

MIT
