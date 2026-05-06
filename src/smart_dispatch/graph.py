from __future__ import annotations

import heapq
import math
from collections import defaultdict

from smart_dispatch.models import Coordinate, GraphEdge


class TravelGraph:
    def __init__(self, edges: list[GraphEdge]) -> None:
        self.nodes: set[Coordinate] = set()
        self.adjacency: dict[Coordinate, list[tuple[Coordinate, float]]] = defaultdict(list)
        for edge in edges:
            self.nodes.add(edge.start)
            self.nodes.add(edge.end)
            weight = edge.effective_minutes
            # The input describes a grid, so we mirror edges for a practical bidirectional road network.
            self.adjacency[edge.start].append((edge.end, weight))
            self.adjacency[edge.end].append((edge.start, weight))
        self._distances = self._precompute_all_pairs()

    def _precompute_all_pairs(self) -> dict[Coordinate, dict[Coordinate, float]]:
        return {node: self._dijkstra(node) for node in self.nodes}

    def _dijkstra(self, source: Coordinate) -> dict[Coordinate, float]:
        distances: dict[Coordinate, float] = {node: math.inf for node in self.nodes}
        distances[source] = 0.0
        heap: list[tuple[float, Coordinate]] = [(0.0, source)]
        while heap:
            current_distance, node = heapq.heappop(heap)
            if current_distance > distances[node]:
                continue
            for neighbor, weight in self.adjacency.get(node, []):
                candidate = current_distance + weight
                if candidate < distances[neighbor]:
                    distances[neighbor] = candidate
                    heapq.heappush(heap, (candidate, neighbor))
        return distances

    def has_node(self, node: Coordinate) -> bool:
        return node in self.nodes

    def travel_minutes(self, start: Coordinate, end: Coordinate) -> float:
        distance = self._distances.get(start, {}).get(end, math.inf)
        return distance
