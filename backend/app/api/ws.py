"""Browser WebSocket: relays live ticks and per-user order/position updates.

Connect with ``/ws?token=<access_token>``. The client may send
``{"action": "subscribe", "keys": [...]}`` / ``{"action": "unsubscribe", ...}``
to control which instruments' ticks it receives. Order/position updates for the
authenticated user are always forwarded.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.security import decode_token
from app.redis_client import (
    ORDER_UPDATES_CHANNEL,
    POSITION_UPDATES_CHANNEL,
    TICKS_CHANNEL,
    redis_client,
    user_channel,
)

logger = logging.getLogger("ws")
router = APIRouter()


@router.websocket("/ws")
async def market_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    try:
        user_id = decode_token(token, "access")
    except JWTError:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    wanted: set[str] = set()

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(
        TICKS_CHANNEL, ORDER_UPDATES_CHANNEL, POSITION_UPDATES_CHANNEL, user_channel(user_id)
    )

    async def pump() -> None:
        async for msg in pubsub.listen():
            if msg.get("type") != "message":
                continue
            channel = msg["channel"]
            data = msg["data"]
            try:
                payload = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue

            if channel == TICKS_CHANNEL:
                if wanted and payload.get("instrument_key") not in wanted:
                    continue
                await websocket.send_json({"type": "tick", "data": payload})
            elif channel in (ORDER_UPDATES_CHANNEL, POSITION_UPDATES_CHANNEL):
                if payload.get("user_id") != user_id:
                    continue
                kind = "order" if channel == ORDER_UPDATES_CHANNEL else "position"
                await websocket.send_json({"type": kind, "data": payload})
            else:  # per-user channel
                await websocket.send_json({"type": payload.get("type", "message"), "data": payload})

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                cmd = json.loads(raw)
            except json.JSONDecodeError:
                continue
            action = cmd.get("action")
            keys = cmd.get("keys", [])
            if action == "subscribe":
                wanted.update(keys)
            elif action == "unsubscribe":
                wanted.difference_update(keys)
            elif action == "set":
                wanted.clear()
                wanted.update(keys)
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task
        await pubsub.close()
