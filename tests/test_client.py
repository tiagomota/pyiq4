"""Tests for RainbirdIQ4Client — all network calls mocked with aioresponses."""

import re

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
                "id": 1, "companyId": 10, "name": "Home", "description": "",
                "timeZone": "Europe/Lisbon", "postalCode": "1000", "numberOfSatellites": 2,
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
                "id": 42, "name": "Garage Controller", "siteId": 1, "siteName": "Home",
                "stationCount": 4, "macAddress": "AA:BB:CC:DD:EE:FF", "version": "4.98",
                "isMQTT": True, "latitude": 38.7, "longitude": -9.1,
                "rainDelay": 0, "simultaneousStations": 1,
                "isShutdown": False, "satelliteEnabled": True,
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
                "id": 100, "name": "Program A", "shortName": "A", "satelliteId": 42,
                "isEnabled": True, "programAdjust": 130, "weekDays": "0101010",
                "skipDays": 0, "number": 1,
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
            "id": 100, "name": "Program A", "shortName": "A", "satelliteId": 42,
            "isEnabled": True, "programAdjust": 100, "weekDays": "1111111",
            "skipDays": 0, "number": 1,
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


class TestUpdateToken:
    def test_update_token_replaces_value(self):
        client = RainbirdIQ4Client.__new__(RainbirdIQ4Client)
        client._access_token = "old_token"
        assert client.access_token == "old_token"
        client.update_token("new_token")
        assert client.access_token == "new_token"
