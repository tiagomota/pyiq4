"""Async REST client for the Rain Bird IQ4 cloud API."""

from __future__ import annotations

from typing import Any

import aiohttp

from .exceptions import RainbirdAPIError, RainbirdAuthError, RainbirdConnectionError
from .models import (
    ConnectionStatus,
    Controller,
    NewProgramStep,
    Program,
    ProgramDetail,
    ProgramStep,
    RuntimeAssignment,
    Site,
    StartTime,
    Station,
    StationRuntime,
)
from .utils import parse_timespan

_API_BASE = "https://iq4server.rainbird.com/coreapi/api"


class RainbirdIQ4Client:
    """Async client for the Rain Bird IQ4 cloud REST API.

    The caller is responsible for creating and closing the
    ``aiohttp.ClientSession`` — this client never creates one internally,
    which is the standard pattern for use inside Home Assistant.

    Args:
        session: An ``aiohttp.ClientSession`` managed by the caller.
        access_token: JWT bearer token obtained from :func:`~pyiq4.auth.authenticate`.
    """

    def __init__(self, session: aiohttp.ClientSession, access_token: str) -> None:
        self._session = session
        self._access_token = access_token

    @property
    def access_token(self) -> str:
        return self._access_token

    def update_token(self, new_token: str) -> None:
        """Replace the current bearer token (called by HA coordinator after reauth)."""
        self._access_token = new_token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | list[tuple[str, str]] | None = None,
        json: Any = None,
    ) -> Any:
        """Perform an authenticated request and return the parsed JSON body.

        Raises:
            RainbirdAuthError: HTTP 401 or 403 (token expired / rejected).
            RainbirdAPIError: Any other non-2xx response.
            RainbirdConnectionError: Transport-level failure.
        """
        url = f"{_API_BASE}/{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            async with self._session.request(
                method, url, headers=headers, params=params, json=json
            ) as resp:
                if resp.status in (401, 403):
                    raise RainbirdAuthError(
                        f"Token rejected by API (HTTP {resp.status}). Re-authentication required.",
                        status_code=resp.status,
                    )
                if not resp.ok:
                    body = await resp.text()
                    raise RainbirdAPIError(
                        f"API error {resp.status} on {method} {path}",
                        status_code=resp.status,
                        response_body=body,
                    )
                if resp.content_type == "application/json":
                    return await resp.json()
                return None
        except aiohttp.ClientError as exc:
            raise RainbirdConnectionError(f"Network error: {exc}") from exc

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------

    async def get_sites(self) -> list[Site]:
        """Return all sites for the authenticated account."""
        data = await self._request("GET", "Site/GetSites")
        return [
            Site(
                id=s["id"],
                company_id=s.get("companyId", 0),
                name=s["name"],
                description=s.get("description", ""),
                time_zone=s.get("timeZone", ""),
                postal_code=s.get("postalCode", ""),
                number_of_satellites=s.get("numberOfSatellites", 0),
            )
            for s in data
        ]

    # ------------------------------------------------------------------
    # Controllers (Satellites)
    # ------------------------------------------------------------------

    async def get_controllers(self) -> list[Controller]:
        """Return all controllers across all sites."""
        data = await self._request("GET", "Satellite/GetSatelliteList")
        return [_parse_controller(c) for c in data]

    async def get_connection_status(self, controller_ids: list[int]) -> list[ConnectionStatus]:
        """Return real-time MQTT connection status for the given controllers."""
        if not controller_ids:
            return []
        # aiohttp supports list-of-tuples for repeated params: ?satelliteIds=X&satelliteIds=Y
        params = [("satelliteIds", str(cid)) for cid in controller_ids]
        data = await self._request("GET", "Satellite/isConnected", params=params)
        # Response is wrapped: {"satellites": [...]}
        satellites = data.get("satellites", data) if isinstance(data, dict) else data
        return [
            ConnectionStatus(
                controller_id=s["id"],
                is_connected=s.get("isConnected", False),
                timestamp=s.get("timestamp", ""),
            )
            for s in satellites
        ]

    # ------------------------------------------------------------------
    # Programs
    # ------------------------------------------------------------------

    async def get_programs(self, controller_id: int) -> list[Program]:
        """Return all programs for a controller."""
        data = await self._request(
            "GET", "Program/GetProgramList", params={"satelliteId": controller_id}
        )
        return [_parse_program(p) for p in data]

    async def get_program_detail(self, program_id: int) -> ProgramDetail:
        """Return the full program object (needed for write operations)."""
        data = await self._request("GET", "Program/GetProgram", params={"programId": program_id})
        return ProgramDetail.from_api_dict(data)

    async def update_program(self, program: ProgramDetail) -> None:
        """Update a program. GET the detail, modify fields, then call this."""
        await self._request("PUT", "Program/UpdateProgram", json=program.to_api_dict())

    # ------------------------------------------------------------------
    # Start times
    # ------------------------------------------------------------------

    async def get_start_times(self, controller_id: int) -> list[StartTime]:
        """Return all start times for programs on a controller.

        Uses the flat GetAllStartTimes endpoint and filters to programs
        belonging to this controller using the program list.
        """
        programs = await self.get_programs(controller_id)
        program_ids = {p.id for p in programs}
        data = await self._request(
            "GET",
            "StartTime/GetAllStartTimes",
            params={"includeProgram": "false", "includeProgramGroup": "false"},
        )
        return [
            _parse_start_time(s)
            for s in (data if isinstance(data, list) else [])
            if s.get("programId") in program_ids
        ]

    async def add_start_time(self, program_id: int, time_of_day: str) -> StartTime:
        """Add a start time to a program.

        Args:
            program_id: Program ID.
            time_of_day: ``"HH:MM"`` in local time.
        """
        payload = {
            "dateTime": f"1999-09-09T{time_of_day}:00",
            "programId": program_id,
            "enabled": True,
        }
        data = await self._request("POST", "StartTime/CreateStartTime", json=payload)
        return _parse_start_time(data)

    async def delete_start_times(self, program_id: int, start_time_ids: list[int]) -> None:
        """Delete start times using the reliable v2 batch endpoint."""
        payload = {
            "add": [],
            "update": [],
            "delete": {"id": program_id, "ids": start_time_ids},
        }
        await self._request("PATCH", "StartTime/v2/UpdateBatches", json=payload)

    # ------------------------------------------------------------------
    # Stations
    # ------------------------------------------------------------------

    async def get_stations(self, controller_id: int) -> list[Station]:
        """Return all stations (valve zones) for a controller."""
        data = await self._request(
            "GET", "Station/GetStationListForSatellite", params={"satelliteId": controller_id}
        )
        return [
            Station(
                id=s["id"],
                controller_id=controller_id,
                name=s["name"],
                terminal=s.get("terminal", 0),
            )
            for s in data
        ]

    # ------------------------------------------------------------------
    # Program steps (runtimes)
    # ------------------------------------------------------------------

    async def get_station_runtimes(self, controller_id: int) -> list[StationRuntime]:
        """Return runtime assignments per station for a controller."""
        data = await self._request(
            "GET",
            "ProgramStep/GetProgramsAssignedAndRunTimeBySatelliteId",
            params={"satelliteId": controller_id},
        )
        result = []
        for item in data:
            assignments = tuple(
                RuntimeAssignment(
                    program_step_id=a["programStepId"],
                    program_id=a["programId"],
                    program_short_name=a.get("programShortName", ""),
                    adjusted_run_time=a.get("adjustedRunTime", "00:00:00"),
                    base_run_time=a.get("baseRunTime", "00:00:00"),
                )
                for a in item.get("runtimeProgramAssignedList", [])
            )
            result.append(StationRuntime(station_id=item["stationId"], assignments=assignments))
        return result

    async def get_program_step(self, step_id: int) -> ProgramStep:
        """Return the full program step (needed for runtime updates)."""
        data = await self._request(
            "GET", "ProgramStep/GetProgramStepById", params={"programStepId": step_id}
        )
        return _parse_program_step(data)

    async def update_program_step(self, step: ProgramStep) -> None:
        """Update a program step's runtime. GET the step, modify, then call this.

        Sends the full struct back — the API will zero out any omitted fields,
        so we must include actionId, companyId, and assetID from the original GET.
        """
        from .utils import format_timespan

        payload = {
            "id": step.id,
            "programId": step.program_id,
            "stationId": step.station_id,
            "sequenceNumber": step.sequence_number,
            "actionId": step.action_id,
            "runTime": format_timespan(step.run_time_ticks),
            "runTimeLong": step.run_time_ticks,
            "companyId": step.company_id,
            "assetID": step.asset_id,
        }
        await self._request("PUT", "ProgramStep/UpdateProgramStep", json=payload)

    async def add_program_steps(self, steps: list[NewProgramStep]) -> None:
        """Assign stations to a program. Runtime defaults to null (set separately)."""
        payload = [
            {
                "actionId": "RunStation",  # must be string, not int
                "programId": str(s.program_id),
                "stationId": s.station_id,
                "runTimeLong": s.run_time_ticks,
            }
            for s in steps
        ]
        await self._request("POST", "ProgramStep/CreateProgramSteps", json=payload)

    async def delete_program_steps(self, step_ids: list[int]) -> None:
        """Remove stations from a program by step ID."""
        await self._request("DELETE", "ProgramStep/DeleteProgramSteps", json=step_ids)


# ------------------------------------------------------------------
# Private parse helpers
# ------------------------------------------------------------------


def _parse_controller(c: dict[str, Any]) -> Controller:
    return Controller(
        id=c["id"],
        name=c["name"],
        site_id=c.get("siteId", 0),
        site_name=c.get("siteName", ""),
        station_count=c.get("stationCount", 0),
        mac_address=c.get("macAddress", ""),
        version=c.get("version", ""),
        is_mqtt=c.get("isMQTT", False),
        latitude=c.get("latitude", 0.0),
        longitude=c.get("longitude", 0.0),
        rain_delay=c.get("rainDelay", 0),
        simultaneous_stations=c.get("simultaneousStations", 1),
        is_shutdown=c.get("isShutdown", False),
        satellite_enabled=c.get("satelliteEnabled", True),
    )


def _parse_program(p: dict[str, Any]) -> Program:
    return Program(
        id=p["id"],
        name=p["name"],
        short_name=p.get("shortName", ""),
        controller_id=p["satelliteId"],
        is_enabled=p.get("isEnabled", True),
        seasonal_adjustment=p.get("programAdjust", 100),
        week_days=p.get("weekDays", "0000000"),
        skip_days=p.get("skipDays", 0),
        number=p.get("number", 1),
    )


def _parse_start_time(s: dict[str, Any]) -> StartTime:
    # DateTime is like "1999-09-09T06:00:00" — only the time part matters.
    dt = s.get("dateTime", s.get("dateTimeLocal", "1999-09-09T00:00:00"))
    time_of_day = dt[11:16] if len(dt) >= 16 else "00:00"
    return StartTime(
        id=s["id"],
        program_id=s["programId"],
        time_of_day=time_of_day,
        enabled=s.get("enabled", True),
    )


def _parse_program_step(s: dict[str, Any]) -> ProgramStep:
    run_time_long = s.get("runTimeLong", 0)
    if not run_time_long and s.get("runTime"):
        run_time_long = parse_timespan(s["runTime"])
    return ProgramStep(
        id=s["id"],
        program_id=s["programId"],
        station_id=s["stationId"],
        run_time_ticks=run_time_long or 0,
        sequence_number=s.get("sequenceNumber", 0),
        action_id=s.get("actionId", 0),
        company_id=s.get("companyId", 0),
        asset_id=s.get("assetID", 0),
    )
