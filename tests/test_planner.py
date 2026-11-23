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

"""Exercise the MCP tools against the bundled collision grid and waypoints."""

import asyncio
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from astar_mcp.server import create_astar_mcp
from slam_map_demo.scripts.nav_service import Planner


MAP = Path(__file__).resolve().parents[1] / "slam_map_demo/maps/room1110/2026-11-11.2"


@pytest.fixture(scope="module")
def planner():
    return Planner(MAP)


@pytest.mark.parametrize("coordinate_goal", [False, True])
def test_mcp_saves_the_exact_planned_route(planner, coordinate_goal):
    async def exercise():
        server = create_astar_mcp(planner, host="127.0.0.1", port=0)
        async with create_connected_server_and_client_session(server) as session:
            waypoints = (await session.call_tool("list_waypoints", {})).structuredContent
            goal = next(p for p in waypoints["waypoints"] if p["name"] == "母婴室")
            target = (
                {key: goal["stand_pose"][key] for key in ("x", "y", "yaw")}
                if coordinate_goal else goal["id"]
            )
            start = {"x": 0.0, "y": 0.0, "yaw": 0.0}
            planned = await session.call_tool("plan_route", {"start": start, "goal": target})
            assert not planned.isError
            summary = planned.structuredContent
            result = await session.call_tool("get_plan", {"plan_id": summary["plan_id"]})
            route = result.structuredContent
            assert route["map_id"] == waypoints["map_id"] == "room1110"
            assert route["map_version"] == waypoints["map_version"] == "2026-11-11.2"
            assert route["start"] == start
            actual = route["legs"][0]["goal"]["stand_pose"]
            assert all(actual[key] == goal["stand_pose"][key] for key in ("x", "y", "yaw"))
            assert route["legs"][0]["path"][0] == [0.0, 0.0]
            assert len(route["legs"][0]["path"]) == summary["path_points"]
            assert (await session.call_tool("get_plan", {"plan_id": "unknown"})).isError

    asyncio.run(exercise())


@pytest.mark.parametrize("goal", [
    ["广告牌", "厕所通道"], {"x": True, "y": 0}, {"x": 1, "y": 0, "speed": 1},
    "", "不存在的导航目的地",
])
def test_mcp_invalid_goals_return_tool_errors(planner, goal):
    async def exercise():
        server = create_astar_mcp(planner, host="127.0.0.1", port=0)
        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool("plan_route", {
                "start": {"x": 0.0, "y": 0.0}, "goal": goal,
            })
            assert result.isError

    asyncio.run(exercise())
