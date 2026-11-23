from typing import Any


class RouteValidationError(ValueError):
    """
    Raised when an optimized route violates completeness, uniqueness,
    or coordinate integrity.
    """


def validate_route(
    original_buildings: list[dict[str, Any]],
    optimized_buildings: list[dict[str, Any]],
    total_distance_km: float,
) -> None:
    """
    Validate that an optimized route strictly satisfies:
    1. Output count exactly equals input building count.
    2. Every eligible building ID appears exactly once (no duplicates, no omissions).
    3. Sequence orders are consecutive integers starting at 1.
    4. All coordinates are within valid geographic bounds.
    5. Route distance is non-negative.
    """
    n_orig = len(original_buildings)
    n_opt = len(optimized_buildings)

    if n_orig != n_opt:
        raise RouteValidationError(
            f"Building count mismatch: original has {n_orig}, optimized has {n_opt}"
        )

    if total_distance_km < 0.0:
        raise RouteValidationError(
            f"Route distance cannot be negative, got {total_distance_km}"
        )

    if n_orig == 0:
        return

    original_ids = {str(b["id"]) for b in original_buildings}
    seen_ids: set[str] = set()

    for idx, b in enumerate(optimized_buildings):
        b_id = str(b.get("id"))
        if not b_id:
            raise RouteValidationError(f"Building at index {idx} has missing ID")

        if b_id in seen_ids:
            raise RouteValidationError(
                f"Duplicate building ID '{b_id}' in optimized route"
            )

        if b_id not in original_ids:
            raise RouteValidationError(
                f"Building ID '{b_id}' does not belong to this HLB"
            )

        seen_ids.add(b_id)

        seq = b.get("sequence_order")
        if seq != idx + 1:
            raise RouteValidationError(
                f"Invalid sequence order at index {idx}: expected {idx + 1}, got {seq}"
            )

        lat = b.get("latitude")
        lon = b.get("longitude")
        if (
            lat is None
            or lon is None
            or not (-90.0 <= lat <= 90.0)
            or not (-180.0 <= lon <= 180.0)
        ):
            raise RouteValidationError(
                f"Building ID '{b_id}' has invalid coordinates: lat={lat}, lon={lon}"
            )
