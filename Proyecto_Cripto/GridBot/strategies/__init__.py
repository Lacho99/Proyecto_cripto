"""
strategies/__init__.py
Módulo de estrategias de trading
"""
from .base import BaseStrategy
from .manual import ManualStrategy
from .grid import GridStrategy
from .gridT import GridTStrategy
from .ema import EMAStrategy
from .scalp import ScalpStrategy