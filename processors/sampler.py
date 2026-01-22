"""Sampling decisions for traces."""

import random
from dataclasses import dataclass


@dataclass
class SamplingResult:
    sampled: bool


class Sampler:
    """Head-based sampler using a fixed probability."""

    def __init__(self, sample_rate: float = 1.0) -> None:
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError("sample_rate must be between 0.0 and 1.0")
        self.sample_rate = sample_rate

    def should_sample(self) -> SamplingResult:
        return SamplingResult(sampled=random.random() <= self.sample_rate)

