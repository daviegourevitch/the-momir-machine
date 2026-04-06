from __future__ import annotations

from typing import Iterable, List


ManaValue = int | float


class RuntimeManaPool:
    def __init__(self, initial_values: Iterable[ManaValue]) -> None:
        self._values: List[ManaValue] = []
        self._index = 0
        self.set_values(list(initial_values))

    @staticmethod
    def _normalize(values: Iterable[ManaValue]) -> List[ManaValue]:
        normalized: List[ManaValue] = []
        seen: set[ManaValue] = set()

        for value in values:
            if not isinstance(value, (int, float)):
                continue
            numeric = float(value)
            clean: ManaValue = int(numeric) if numeric.is_integer() else numeric
            if clean in seen:
                continue
            seen.add(clean)
            normalized.append(clean)

        normalized.sort()
        return normalized

    def set_values(self, values: Iterable[ManaValue], preferred_value: ManaValue | None = None) -> None:
        normalized = self._normalize(values)
        if not normalized:
            return

        self._values = normalized
        if preferred_value is None:
            self._index = min(self._index, len(self._values) - 1)
            return

        preferred = float(preferred_value)
        best_index = 0
        best_distance = abs(float(self._values[0]) - preferred)
        for idx in range(1, len(self._values)):
            distance = abs(float(self._values[idx]) - preferred)
            if distance < best_distance:
                best_index = idx
                best_distance = distance
        self._index = best_index

    def current(self) -> ManaValue:
        return self._values[self._index]

    def step(self, delta: int) -> ManaValue:
        if not self._values:
            raise RuntimeError("RuntimeManaPool has no values")
        self._index = (self._index + delta) % len(self._values)
        return self.current()

    def values(self) -> List[ManaValue]:
        return list(self._values)
