import {describe,it,expect} from 'vitest';
import {selectTrade, adjacentTrade, tradeAtTime} from './selection';
// Explicitly SYNTHETIC unit fixtures. Never used by production API/UI.
const trades = [{id:'closed-0001',entry_time:'2024-01-01T00:00:00Z',exit_time:'2024-01-02T00:00:00Z'},{id:'open-0001',entry_time:'2024-01-03T00:00:00Z',exit_time:null}];
describe('scope-safe trade selection',()=>{
 it('clears selection absent from the new scope',()=>{expect(selectTrade(trades,'old-scope')).toBe(null);expect(selectTrade(trades,'closed-0001')?.id).toBe('closed-0001');});
 it('moves within bounds without fabricating trades',()=>{expect(adjacentTrade(trades,'closed-0001',1)).toBe('open-0001');expect(adjacentTrade(trades,'open-0001',1)).toBe('open-0001');expect(adjacentTrade([],null,1)).toBe(null);});
 it('opens exact matching saved execution only',()=>{expect(tradeAtTime([{time:100,trade_id:'closed-0001'}],100)).toBe('closed-0001');expect(tradeAtTime([{time:100,trade_id:'closed-0001'}],101)).toBe(null);});
});