# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0

"""Serve the local A* planner over Streamable HTTP MCP."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from pydantic import BaseModel, ConfigDict

from slam_map_demo.scripts.nav_service import Planner


class CoordinateGoal(BaseModel):
    """A map-frame goal in meters, with an optional final yaw in radians."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    x: float
    y: float
    yaw: float | None = None


NavigationGoal = str | CoordinateGoal


def create_astar_mcp(planner: Planner, *, host: str, port: int) -> FastMCP:
    """Expose waypoints and saved routes from the configured map."""
    server = FastMCP(
        "unitree-navigation",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )
    readonly = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
    plans: dict[str, dict[str, Any]] = {}

    @server.tool(annotations=readonly)
    def list_waypoints() -> dict[str, Any]:
        """List the map's named destinations and standing poses."""
        return {
            "ok": True,
            "map_id": planner.map_id,
            "map_version": planner.map_version,
            "waypoints": planner.waypoint_list(),
        }

    @server.tool(annotations=readonly)
    async def plan_route(start: CoordinateGoal, goal: NavigationGoal) -> dict[str, Any]:
        """Plan to one target from the fresh simulator x, y and yaw and return a plan_id for follow_plan."""
        target = goal.model_dump(exclude_none=True) if isinstance(goal, CoordinateGoal) else goal
        route = await asyncio.to_thread(
            planner.plan, start.model_dump(exclude_none=True), [target]
        )
        plan_id = f"plan_{uuid4().hex}"
        plans[plan_id] = route
        if len(plans) > 256:
            del plans[next(iter(plans))]
        return {
            "ok": True,
            "plan_id": plan_id,
            "map_id": route["map_id"],
            "map_version": route["map_version"],
            "goal": route["legs"][0]["goal"],
            "total_length": route["total_length"],
            "path_points": len(route["legs"][0]["path"]),
            "warnings": route.get("warnings", []),
        }

    @server.tool(annotations=readonly)
    def get_plan(plan_id: str) -> dict[str, Any]:
        """Return the exact route saved by plan_route for the simulation service."""
        if plan_id not in plans:
            raise ValueError("unknown plan_id; plan again from the current pose")
        return plans[plan_id]

    return server


def main() -> None:
    """Serve the configured A* planner over MCP."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", default=os.environ.get("ROBOT_MAP", "room1110/2026-11-11.2"),
                        help="map/version under slam_map_demo/maps, or an absolute map directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    maps = Path(__file__).resolve().parents[1] / "slam_map_demo/maps"
    planner = Planner(maps / args.map)
    create_astar_mcp(planner, host=args.host, port=args.port).run(transport="streamable-http")


if __name__ == "__main__":
    main()
