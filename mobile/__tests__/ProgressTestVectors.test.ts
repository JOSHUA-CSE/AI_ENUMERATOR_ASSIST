import { calculateAuthoritativeProgress } from '../src/core/progressService';
import progressVectors from './fixtures/progress_test_vectors.json';

describe('Progress Test Vectors (Shared JSON Invariant)', () => {
  it('loads test cases properly', () => {
    expect(progressVectors.test_cases).toBeDefined();
    expect(progressVectors.test_cases.length).toBeGreaterThan(0);
  });

  progressVectors.test_cases.forEach((tc) => {
    it(`evaluates ${tc.id}: ${tc.description}`, () => {
      const result = calculateAuthoritativeProgress(tc.buildings as any);

      expect(result.total_eligible_buildings).toBe(tc.expected.total_eligible_buildings);
      expect(result.completed_buildings).toBe(tc.expected.completed_buildings);
      expect(result.pending_buildings).toBe(tc.expected.pending_buildings);
      expect(result.resolved_census_houses).toBe(tc.expected.resolved_census_houses);
      expect(result.locked_census_houses).toBe(tc.expected.locked_census_houses);
      expect(result.unresolved_census_houses).toBe(tc.expected.unresolved_census_houses);
      expect(result.completion_percentage).toBeCloseTo(tc.expected.completion_percentage, 2);
    });
  });
});

