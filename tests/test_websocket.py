from unittest.mock import AsyncMock

import pytest

from pulsecheck.ws import ConnectionManager


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_connect_adds_client(self):
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        ws.accept.assert_called_once()
        assert len(mgr._connections) == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self):
        mgr = ConnectionManager()
        ws = AsyncMock()
        await mgr.connect(ws)
        mgr.disconnect(ws)
        assert len(mgr._connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await mgr.connect(ws1)
        await mgr.connect(ws2)

        msg = {"type": "health_check", "status": "healthy"}
        await mgr.broadcast(msg)

        ws1.send_json.assert_called_once_with(msg)
        ws2.send_json.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected_clients(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws2.send_json.side_effect = Exception("connection closed")

        await mgr.connect(ws1)
        await mgr.connect(ws2)

        msg = {"type": "test"}
        await mgr.broadcast(msg)

        # ws2 should have been removed
        assert len(mgr._connections) == 1
        assert mgr._connections[0] is ws1

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self):
        mgr = ConnectionManager()
        await mgr.broadcast({"type": "test"})  # should not raise

    @pytest.mark.asyncio
    async def test_multiple_connects_and_disconnects(self):
        mgr = ConnectionManager()
        clients = [AsyncMock() for _ in range(5)]
        for c in clients:
            await mgr.connect(c)
        assert len(mgr._connections) == 5

        mgr.disconnect(clients[2])
        assert len(mgr._connections) == 4
        assert clients[2] not in mgr._connections
