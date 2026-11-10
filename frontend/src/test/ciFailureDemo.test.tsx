import { describe, it, expect } from 'vitest';

describe('ci failure demonstration', () => {
  it('is deliberately red for the failure-injection drill', () => {
    expect(true).toBe(false);
  });
});
