/**
 * Authoritative Fieldwork Progress Engine (Mobile Port)
 * Strictly mirrors backend `AuthoritativeProgressService`.
 * Enforces:
 *   1. FALSE_DETECTION buildings excluded from progress denominators.
 *   2. Building complete iff `listing_closed === true` AND `census_houses.length > 0`
 *      AND all census houses are resolved (LISTED, VACANT, NON_RESIDENTIAL).
 *   3. LOCKED census houses pending revisit prevent building completion.
 *   4. An empty building (0 census houses) must NOT automatically become complete.
 */

export interface CensusHouseProgressInput {
  id?: string;
  listing_state: 'NOT_VISITED' | 'LISTED' | 'VACANT' | 'NON_RESIDENTIAL' | 'LOCKED' | string;
}

export interface BuildingProgressInput {
  id?: string;
  listing_closed: boolean;
  field_status: 'UNVERIFIED' | 'CONFIRMED' | 'FALSE_DETECTION' | 'FIELD_ADDED' | string;
  census_houses?: CensusHouseProgressInput[];
}

export interface AuthoritativeProgressResult {
  total_eligible_buildings: number;
  completed_buildings: number;
  pending_buildings: number;
  resolved_census_houses: number;
  locked_census_houses: number;
  unresolved_census_houses: number;
  completion_percentage: number;
}

export function calculateAuthoritativeProgress(
  buildings: BuildingProgressInput[]
): AuthoritativeProgressResult {
  let totalEligibleBuildings = 0;
  let completedBuildings = 0;
  let resolvedCensusHouses = 0;
  let lockedCensusHouses = 0;
  let unresolvedCensusHouses = 0;

  for (const b of buildings) {
    const fStatus = String(b.field_status || 'UNVERIFIED').toUpperCase();
    if (fStatus === 'FALSE_DETECTION') {
      continue; // Excluded from progress denominator
    }

    totalEligibleBuildings += 1;
    const listingClosed = Boolean(b.listing_closed);
    const censusHouses = b.census_houses || [];

    let hasLocked = false;
    let allResolved = censusHouses.length > 0; // Empty building cannot become complete

    for (const ch of censusHouses) {
      const state = String(ch.listing_state || 'NOT_VISITED').toUpperCase();
      if (state === 'LISTED' || state === 'VACANT' || state === 'NON_RESIDENTIAL') {
        resolvedCensusHouses += 1;
      } else if (state === 'LOCKED') {
        lockedCensusHouses += 1;
        hasLocked = true;
        allResolved = false;
      } else {
        // NOT_VISITED or unresolved
        unresolvedCensusHouses += 1;
        allResolved = false;
      }
    }

    if (listingClosed && allResolved) {
      completedBuildings += 1;
    }
  }

  const pendingBuildings = Math.max(0, totalEligibleBuildings - completedBuildings);
  const completionPercentage =
    totalEligibleBuildings > 0
      ? Math.round((completedBuildings / totalEligibleBuildings) * 10000) / 100
      : 0.0;

  return {
    total_eligible_buildings: totalEligibleBuildings,
    completed_buildings: completedBuildings,
    pending_buildings: pendingBuildings,
    resolved_census_houses: resolvedCensusHouses,
    locked_census_houses: lockedCensusHouses,
    unresolved_census_houses: unresolvedCensusHouses,
    completion_percentage: completionPercentage,
  };
}

export const progressService = {
  calculateAuthoritativeProgress,
};

