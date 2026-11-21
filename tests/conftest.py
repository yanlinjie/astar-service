# Copyright 2026 The RPent Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""An in-memory HTTP boundary for environments where loopback sockets are blocked."""

from __future__ import annotations

import json
import math
from types import SimpleNamespace

import httpx
import pytest

from astar_mcp.navigation_client import NavigationClient


@pytest.fixture
def navigation_services():
    identity = {"map_id": "test_room", "map_version": "v1"}
    state = SimpleNamespace(requests=[], plan_mutator=None)
    waypoints = [
        {
            "id": "wp_01",
            "name": "广告牌",
            "stand_pose": {"x": 1.0, "y": 0.0, "yaw": 0.0},
        },
        {
            "id": "wp_02",
            "name": "厕所",
            "stand_pose": {"x": 1.0, "y": 1.0, "yaw": 1.57},
        },
    ]

    def response(request):
        payload = json.loads(request.content) if request.content else None
        path = request.url.path
        state.requests.append((request.method, request.url.host, path, payload))
        if request.url.host == "nav.test":
            if path == "/health":
                return httpx.Response(
                    200, json={"ok": True, **identity, "waypoints": 2}
                )
            if path == "/waypoints":
                return httpx.Response(
                    200, json={"ok": True, **identity, "waypoints": waypoints}
                )
            if path == "/plan":
                legs = []
                start = payload["start"]
                previous = [start["x"], start["y"]]
                for query in payload["goals"]:
                    if isinstance(query, str):
                        goal = next(
                            (g for g in waypoints if query in (g["id"], g["name"])),
                            None,
                        )
                        if goal is None:
                            return httpx.Response(
                                400,
                                json={"ok": False, "error": "unknown destination"},
                            )
                    else:
                        goal = {
                            "id": "xy",
                            "name": "coordinate",
                            "stand_pose": {**query, "yaw": query.get("yaw")},
                        }
                    target = goal["stand_pose"]
                    dx, dy = target["x"] - previous[0], target["y"] - previous[1]
                    path_points = [previous, [target["x"], target["y"]]]
                    legs.append(
                        {
                            "query": query,
                            "goal": goal,
                            "path": path_points,
                            "headings": [math.atan2(dy, dx)],
                            "length": math.hypot(dx, dy),
                        }
                    )
                    previous = path_points[-1]
                result = {
                    "ok": True,
                    **identity,
                    "frame": "map",
                    "units": {"length": "meter", "angle": "radian"},
                    "start": start,
                    "goals": [g["goal"]["id"] for g in legs],
                    "legs": legs,
                    "total_length": sum(g["length"] for g in legs),
                    "warnings": [],
                }
                if state.plan_mutator:
                    state.plan_mutator(result)
                return httpx.Response(200, json=result)

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        yield SimpleNamespace(
            state=state, nav=NavigationClient("http://nav.test", client=client)
        )
