"""Hydrological preprocessing for DEM conditioning, flow routing, and drainage.

Implements standard hydrological workflows:
1. Sink filling / depression conditioning (Priority-Flood / Planchon-Darboux)
2. D8 Flow direction
3. D8 Flow accumulation
4. Topographic Wetness Index (TWI) and normalized drainage score (0-100)
"""
from __future__ import annotations

import heapq
from typing import Tuple

import numpy as np


def fill_depressions(elevation: np.ndarray, epsilon: float = 1e-5) -> np.ndarray:
    """Fill depressions/sinks using the priority-flood algorithm.
    
    Ensures every inland cell has a monotonically non-increasing flow path to an outlet
    (boundary or nodata), adding a microscopic gradient (epsilon) across flat sink bottoms.
    """
    rows, cols = elevation.shape
    filled = np.full_like(elevation, np.inf, dtype=np.float64)
    valid_mask = np.isfinite(elevation)
    
    if not np.any(valid_mask):
        return elevation.copy()
        
    heap: list[tuple[float, int, int]] = []
    
    # Initialize boundary and border-of-nodata cells as outlets
    d_rc = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    
    for r in range(rows):
        for c in range(cols):
            if not valid_mask[r, c]:
                continue
            # Check if cell is on the outer boundary or adjacent to a NaN/invalid cell
            is_outlet = (r == 0 or r == rows - 1 or c == 0 or c == cols - 1)
            if not is_outlet:
                for dr, dc in d_rc:
                    nr, nc = r + dr, c + dc
                    if not (0 <= nr < rows and 0 <= nc < cols) or not valid_mask[nr, nc]:
                        is_outlet = True
                        break
            if is_outlet:
                filled[r, c] = float(elevation[r, c])
                heapq.heappush(heap, (float(elevation[r, c]), r, c))
                
    while heap:
        spill_elev, r, c = heapq.heappop(heap)
        for dr, dc in d_rc:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and valid_mask[nr, nc]:
                if filled[nr, nc] == np.inf:
                    target = max(float(elevation[nr, nc]), spill_elev + epsilon)
                    filled[nr, nc] = target
                    heapq.heappush(heap, (target, nr, nc))
                    
    # Restore NaNs where original was invalid
    filled[~valid_mask] = np.nan
    return filled.astype(elevation.dtype)


def compute_d8_flow_direction(
    filled_elevation: np.ndarray,
    dy: float = 1.0,
    dx: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute D8 steepest downslope flow direction.
    
    Returns:
        target_cells: array of shape (rows, cols, 2) with (target_row, target_col) or (-1, -1) for outlets.
        slopes: array of shape (rows, cols) with steepest descent gradient (drop/distance).
    """
    rows, cols = filled_elevation.shape
    d_rc = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    dist = [float(np.hypot(dr * dy, dc * dx)) for dr, dc in d_rc]
    
    target_cells = np.full((rows, cols, 2), -1, dtype=np.int32)
    max_slopes = np.zeros((rows, cols), dtype=np.float32)
    valid_mask = np.isfinite(filled_elevation)
    
    for r in range(rows):
        for c in range(cols):
            if not valid_mask[r, c]:
                continue
            curr_elev = filled_elevation[r, c]
            best_slope = 0.0
            best_target = (-1, -1)
            for (dr, dc), d in zip(d_rc, dist):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and valid_mask[nr, nc]:
                    drop = curr_elev - filled_elevation[nr, nc]
                    slope = drop / d
                    if slope > best_slope:
                        best_slope = slope
                        best_target = (nr, nc)
            target_cells[r, c] = best_target
            max_slopes[r, c] = float(best_slope)
            
    return target_cells, max_slopes


def compute_d8_flow_accumulation(
    filled_elevation: np.ndarray,
    target_cells: np.ndarray,
) -> np.ndarray:
    """Compute upslope contributing area (flow accumulation in cell count) along D8 routing.
    
    Traverses cells in descending order of conditioned elevation so all upstream
    contributions are finalized before routing onward.
    """
    rows, cols = filled_elevation.shape
    valid_mask = np.isfinite(filled_elevation)
    accumulation = np.zeros((rows, cols), dtype=np.float32)
    accumulation[valid_mask] = 1.0  # each cell contributes its own unit area
    
    # Sort valid cells from highest elevation to lowest elevation
    valid_indices = np.where(valid_mask.ravel())[0]
    elevations = filled_elevation.ravel()[valid_indices]
    sorted_order = valid_indices[np.argsort(-elevations)]
    
    for idx in sorted_order:
        r, c = divmod(int(idx), cols)
        tr, tc = target_cells[r, c]
        if tr != -1 and tc != -1 and valid_mask[tr, tc]:
            accumulation[tr, tc] += accumulation[r, c]
            
    accumulation[~valid_mask] = np.nan
    return accumulation


def compute_drainage_and_twi(
    elevation: np.ndarray,
    slope_degrees: np.ndarray,
    dy: float = 1.0,
    dx: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run full hydrological conditioning pipeline to derive measured drainage features.
    
    Returns:
        filled_dem: hydrologically conditioned elevation.
        flow_accumulation: upslope contributing area (cells).
        drainage_score: normalized civil/hydrological drainage score [0, 100].
    """
    filled_dem = fill_depressions(elevation)
    target_cells, _ = compute_d8_flow_direction(filled_dem, dy=dy, dx=dx)
    flow_acc = compute_d8_flow_accumulation(filled_dem, target_cells)
    
    # Compute Topographic Wetness Index (TWI) = ln(a / tan(beta))
    # a: specific catchment area ~ flow_accumulation * cell_size
    cell_width = float(np.sqrt(dy * dx))
    specific_catchment_area = flow_acc * cell_width
    slope_rad = np.radians(np.clip(slope_degrees, 0.05, 89.0))
    tan_slope = np.tan(slope_rad)
    
    valid_mask = np.isfinite(flow_acc) & np.isfinite(slope_degrees) & (flow_acc > 0)
    twi = np.full_like(elevation, np.nan, dtype=np.float32)
    twi[valid_mask] = np.log(specific_catchment_area[valid_mask] / tan_slope[valid_mask])
    
    # Drainage score: 0 to 100
    # High TWI (flat lowlands, confluence valleys, poor runoff) -> lower drainage capacity
    # Low TWI (steep slopes, well-drained hills/ridges) -> higher drainage capacity
    drainage_score = np.full_like(elevation, np.nan, dtype=np.float32)
    if np.any(valid_mask):
        p1 = float(np.nanpercentile(twi[valid_mask], 2.0))
        p99 = float(np.nanpercentile(twi[valid_mask], 98.0))
        span = max(p99 - p1, 1e-4)
        normalized = np.clip((twi[valid_mask] - p1) / span, 0.0, 1.0)
        # Invert so higher score = better drainage
        drainage_score[valid_mask] = np.round((1.0 - normalized) * 100.0, 1)
        
    return filled_dem, flow_acc, drainage_score
