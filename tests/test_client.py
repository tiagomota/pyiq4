"""Tests for RainbirdIQ4Client — all network calls mocked with aioresponses."""

import re
from datetime import UTC, datetime

import aiohttp
import pytest
from aioresponses import aioresponses

from pyiq4 import RainbirdIQ4Client
from pyiq4.exceptions import RainbirdAPIError, RainbirdAuthError

_API = "https://iq4server.rainbird.com/coreapi/api"
_TOKEN = "fake_jwt_token"


class TestGetSites:
    async def test_returns_sites(self):
        payload = [
            {
                "id": 1,
                "companyId": 10,
                "name": "Home",
                "description": "",
                "timeZone": "Europe/Lisbon",
                "postalCode": "1000",
                "numberOfSatellites": 2,
            }
        ]
        with aioresponses() as m:
            m.get(f"{_API}/Site/GetSites", payload=payload)
            async with aiohttp.ClientSession() as session:
                client = RainbirdIQ4Client(session, _TOKEN)
                sites = await client.get_sites()

        assert len(sites) == 1
        assert sites[0].id == 1
        assert sites[0].name == "Home"

    async def test_raises_auth_error_on_401(self):
        with aioresponses() as m:
            m.get(f"{_API}/Site/GetSites", status=401)
            async with aiohttp.ClientSession() as session:
                client = RainbirdIQ4Client(session, _TOKEN)
                with pytest.raises(RainbirdAuthError) as exc_info:
                    await client.get_sites()
        assert exc_info.value.status_code == 401

    async def test_raises_api_error_on_500(self):
        with aioresponses() as m:
            m.get(f"{_API}/Site/GetSites", status=500, body="Internal error")
            async with aiohttp.ClientSession() as session:
                client = RainbirdIQ4Client(session, _TOKEN)
                with pytest.raises(RainbirdAPIError) as exc_info:
                    await client.get_sites()
        assert exc_info.value.status_code == 500


class TestGetControllers:
    async def test_returns_controllers(self):
        payload = [
            {
                "id": 42,
                "name": "Garage Controller",
                "siteId": 1,
                "siteName": "Home",
                "stationCount": 4,
                "macAddress": "AA:BB:CC:DD:EE:FF",
                "version": "4.98",
                "isMQTT": True,
                "latitude": 38.7,
                "longitude": -9.1,
                "rainDelay": 0,
                "simultaneousStations": 1,
                "isShutdown": False,
                "satelliteEnabled": True,
            }
        ]
        with aioresponses() as m:
            m.get(f"{_API}/Satellite/GetSatelliteList", payload=payload)
            async with aiohttp.ClientSession() as session:
                controllers = await RainbirdIQ4Client(session, _TOKEN).get_controllers()

        assert len(controllers) == 1
        assert controllers[0].id == 42
        assert controllers[0].is_mqtt is True


class TestGetPrograms:
    async def test_returns_programs(self):
        payload = [
            {
                "id": 100,
                "name": "Program A",
                "shortName": "A",
                "satelliteId": 42,
                "isEnabled": True,
                "programAdjust": 130,
                "weekDays": "0101010",
                "skipDays": 0,
                "number": 1,
            }
        ]
        with aioresponses() as m:
            m.get(re.compile(rf"{re.escape(_API)}/Program/GetProgramList.*"), payload=payload)
            async with aiohttp.ClientSession() as session:
                programs = await RainbirdIQ4Client(session, _TOKEN).get_programs(42)

        assert len(programs) == 1
        assert programs[0].seasonal_adjustment == 130
        assert programs[0].week_days == "0101010"


class TestProgramDetail:
    async def test_round_trip_preserves_extra_fields(self):
        payload = {
            "id": 100,
            "name": "Program A",
            "shortName": "A",
            "satelliteId": 42,
            "isEnabled": True,
            "programAdjust": 100,
            "weekDays": "1111111",
            "skipDays": 0,
            "number": 1,
            "unknownField": "someValue",  # must survive round-trip
            "etAdjustType": 2,
        }
        with aioresponses() as m:
            m.get(re.compile(rf"{re.escape(_API)}/Program/GetProgram.*"), payload=payload)
            async with aiohttp.ClientSession() as session:
                detail = await RainbirdIQ4Client(session, _TOKEN).get_program_detail(100)

        api_dict = detail.to_api_dict()
        assert api_dict["unknownField"] == "someValue"
        assert api_dict["etAdjustType"] == 2
        assert api_dict["name"] == "Program A"


class TestGetRainDelayConfig:
    async def test_returns_rain_delay_config(self):
        payload = {
            "id": 390353,
            "rainDelayDaysRemaining": 2,
            "rainDelayLong": 1728000000000,
            "rainDelayStart": "2026-04-16T08:37:42",
            "programmingResumes": "2026-04-18T08:37:42",
            "useForecast": False,
            "forecastPercentLimit": 70,
            "forecastInchesLimit": 0.5,
            "forecastDelayDays": 1,
        }
        with aioresponses() as m:
            m.get(re.compile(rf"{re.escape(_API)}/Satellite/GetSatellite.*"), payload=payload)
            async with aiohttp.ClientSession() as session:
                config = await RainbirdIQ4Client(session, _TOKEN).get_rain_delay_config(390353)

        assert config.controller_id == 390353
        assert config.rain_delay_days == 2
        assert config.rain_delay_long == 1728000000000
        assert config.rain_delay_start == "2026-04-16T08:37:42"
        assert config.programming_resumes == "2026-04-18T08:37:42"
        assert config.use_forecast is False
        assert config.forecast_percent_limit == 70
        assert config.forecast_inches_limit == 0.5
        assert config.forecast_delay_days == 1

    async def test_no_active_delay(self):
        payload = {
            "id": 390353,
            "rainDelayDaysRemaining": 0,
            "rainDelayLong": 0,
            "rainDelayStart": None,
            "programmingResumes": None,
            "useForecast": True,
            "forecastPercentLimit": 80,
            "forecastInchesLimit": 0.25,
            "forecastDelayDays": 2,
        }
        with aioresponses() as m:
            m.get(re.compile(rf"{re.escape(_API)}/Satellite/GetSatellite.*"), payload=payload)
            async with aiohttp.ClientSession() as session:
                config = await RainbirdIQ4Client(session, _TOKEN).get_rain_delay_config(390353)

        assert config.rain_delay_days == 0
        assert config.use_forecast is True
        assert config.forecast_delay_days == 2


class TestSetRainDelay:
    async def test_sends_correct_patch(self):
        fixed_time = datetime(2026, 4, 16, 8, 37, 42, tzinfo=UTC)
        with aioresponses() as m:
            m.patch(f"{_API}/Satellite/V2/UpdateBatches", payload=None)
            async with aiohttp.ClientSession() as session:
                await RainbirdIQ4Client(session, _TOKEN).set_rain_delay(
                    390353, delay_days=2, start_time=fixed_time
                )
            request = list(m.requests.values())[0][0]

        body = request.kwargs["json"]
        assert body["ids"] == [390353]
        patches = {p["path"]: p["value"] for p in body["patch"]}
        assert patches["/rainDelayLong"] == 1728000000000  # 2 days in ticks
        assert patches["/rainDelayStart"] == "2026-04-16T08:37:42+0000"

    async def test_cancel_delay_sends_zero_ticks(self):
        fixed_time = datetime(2026, 4, 16, 8, 37, 42, tzinfo=UTC)
        with aioresponses() as m:
            m.patch(f"{_API}/Satellite/V2/UpdateBatches", payload=None)
            async with aiohttp.ClientSession() as session:
                await RainbirdIQ4Client(session, _TOKEN).set_rain_delay(
                    390353, delay_days=0, start_time=fixed_time
                )
            request = list(m.requests.values())[0][0]

        patches = {p["path"]: p["value"] for p in request.kwargs["json"]["patch"]}
        assert patches["/rainDelayLong"] == 0


class TestSetForecastConfig:
    async def test_sends_correct_patch(self):
        with aioresponses() as m:
            m.patch(f"{_API}/Satellite/V2/UpdateBatches", payload=None)
            async with aiohttp.ClientSession() as session:
                await RainbirdIQ4Client(session, _TOKEN).set_forecast_config(
                    390353,
                    use_forecast=True,
                    percent_limit=70,
                    inches_limit=0.5,
                    delay_days=1,
                )
            request = list(m.requests.values())[0][0]

        body = request.kwargs["json"]
        assert body["ids"] == [390353]
        patches = {p["path"]: p["value"] for p in body["patch"]}
        assert patches["/useForecast"] == 1
        assert patches["/forecastPercentLimit"] == 70
        assert patches["/forecastInchesLimit"] == 0.5
        assert patches["/forecastDelayDays"] == 1

    async def test_disable_forecast_sends_zero(self):
        with aioresponses() as m:
            m.patch(f"{_API}/Satellite/V2/UpdateBatches", payload=None)
            async with aiohttp.ClientSession() as session:
                await RainbirdIQ4Client(session, _TOKEN).set_forecast_config(
                    390353, use_forecast=False
                )
            request = list(m.requests.values())[0][0]

        patches = {p["path"]: p["value"] for p in request.kwargs["json"]["patch"]}
        assert patches["/useForecast"] == 0


class TestStartProgram:
    async def test_sends_program_id(self):
        with aioresponses() as m:
            m.post(f"{_API}/ManualOps/StartPrograms", payload=None)
            async with aiohttp.ClientSession() as session:
                await RainbirdIQ4Client(session, _TOKEN).start_program(2294964)
            request = list(m.requests.values())[0][0]

        assert request.kwargs["json"] == [2294964]

    async def test_raises_api_error_on_failure(self):
        with aioresponses() as m:
            m.post(f"{_API}/ManualOps/StartPrograms", status=500, body="error")
            async with aiohttp.ClientSession() as session:
                with pytest.raises(RainbirdAPIError):
                    await RainbirdIQ4Client(session, _TOKEN).start_program(2294964)


class TestStopAllIrrigation:
    async def test_sends_controller_id(self):
        with aioresponses() as m:
            m.post(f"{_API}/Satellite/StopAllIrrigation", payload=None)
            async with aiohttp.ClientSession() as session:
                await RainbirdIQ4Client(session, _TOKEN).stop_all_irrigation(390353)
            request = list(m.requests.values())[0][0]

        assert request.kwargs["json"] == [390353]


class TestUpdateToken:
    def test_update_token_replaces_value(self):
        client = RainbirdIQ4Client.__new__(RainbirdIQ4Client)
        client._access_token = "old_token"
        assert client.access_token == "old_token"
        client.update_token("new_token")
        assert client.access_token == "new_token"
