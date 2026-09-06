"""Planta virtual reproducible. No depende de Flask ni de hardware."""

import math
import random
import time

from app.models.repository import number

DEFAULT_VARIABLES = {
    "ph": {"initial": 6.2, "min": 4, "max": 9, "noise": 0.003, "unit": "pH"},
    "tds": {"initial": 850, "min": 400, "max": 1500, "noise": 0.5, "unit": "ppm"},
    "temperatura_agua": {"initial": 22.4, "min": 15, "max": 32, "noise": 0.02, "unit": "°C"},
    "temperatura_ambiente": {"initial": 27.2, "min": 15, "max": 38, "noise": 0.04, "unit": "°C"},
    "humedad": {"initial": 65, "min": 20, "max": 95, "noise": 0.1, "unit": "%"},
    "nivel": {"initial": 78, "min": 0, "max": 100, "noise": 0.01, "unit": "%"},
}


class Plant:
    def __init__(self, variables=None, seed=42):
        self.variables = variables or DEFAULT_VARIABLES
        if set(self.variables) != set(DEFAULT_VARIABLES):
            raise ValueError("La simulación requiere las seis variables")
        for name, spec in self.variables.items():
            number(spec["min"], "min", -10000, 10000)
            number(spec["max"], "max", spec["min"] + 0.001, 10000)
            number(spec["initial"], "initial", spec["min"], spec["max"])
            number(spec["noise"], "noise", 0, 10)
            if spec["unit"] != DEFAULT_VARIABLES[name]["unit"]:
                raise ValueError("Unidad simulada inválida")
        self.values = {name: spec["initial"] for name, spec in self.variables.items()}
        self.random = random.Random(seed)
        self.output = 0.0
        self.expires = 0.0

    def command(self, output, ttl=3, now=None):
        self.output = number(output, "output", -40, 40)
        ttl = number(ttl, "ttl", 0, 3)
        self.expires = (time.monotonic() if now is None else now) + ttl

    def disturbance(self, variable, delta):
        if variable not in self.variables:
            raise ValueError("Variable desconocida")
        delta = number(delta, "delta", -1000, 1000)
        spec = self.variables[variable]
        self.values[variable] = max(spec["min"], min(spec["max"], self.values[variable] + delta))

    def step(self, dt, now=None):
        dt = number(dt, "dt", 0.001, 10)
        now = time.monotonic() if now is None else now
        if now >= self.expires:
            self.output = 0
        for name, spec in self.variables.items():
            value = self.values[name]
            # pH tiene inercia: no vuelve por sí solo al setpoint.
            drift = 0 if name == "ph" else (spec["initial"] - value) * 0.002 * dt
            noise = self.random.uniform(-spec["noise"], spec["noise"]) * math.sqrt(dt)
            actuation = self.output * 0.0025 * dt if name == "ph" else 0
            self.values[name] = max(spec["min"], min(spec["max"], value + drift + noise + actuation))
        return {name: round(value, 4) for name, value in self.values.items()}
