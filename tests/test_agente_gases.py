"""Tests del Agente de Gases."""
import pytest
import httpx
import asyncio

BASE = "http://localhost:8001"

@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ACTIVO"

@pytest.mark.asyncio
async def test_analizar_normal():
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/analizar", json={
            "zona": "Frente_A_Sogamoso",
            "CH4": 0.4, "CO": 12, "CO2": 0.15, "O2": 20.9, "H2S": 0.3
        })
    assert r.status_code == 200
    data = r.json()
    assert data["nivel_riesgo"] == "SEGURO"
    assert data["gases_criticos"] == []

@pytest.mark.asyncio
async def test_analizar_evacuacion():
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/analizar", json={
            "zona": "Frente_A_Sogamoso",
            "CH4": 5.5, "CO": 250, "CO2": 0.9, "O2": 17.5, "H2S": 55
        })
    assert r.status_code == 200
    data = r.json()
    assert data["nivel_riesgo"] == "EVACUACIÓN INMEDIATA"
    assert len(data["gases_criticos"]) > 0