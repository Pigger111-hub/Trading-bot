import { describe, it, expect } from 'vitest';
import { number, percent } from './format';
describe('missing and saved numerical values', () => {
 it('never converts missing or invalid values to zero', () => { expect(number(null)).toBe('—'); expect(number(undefined)).toBe('—'); expect(number(NaN)).toBe('—'); });
 it('formats actual zero and signed percentages', () => { expect(number(0)).toBe('0.00'); expect(percent(1.25)).toBe('+1.25%'); expect(percent(-2)).toBe('-2.00%'); expect(percent(null)).toBe('—'); });
});