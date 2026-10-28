export function selectTrade<T extends {id:string}>(trades:T[], id:string|null):T|null { return trades.find(t=>t.id===id)??null; }
export function adjacentTrade(trades:{id:string}[], id:string|null, delta:number):string|null { if(!trades.length)return null; const i=trades.findIndex(t=>t.id===id);return trades[Math.min(trades.length-1,Math.max(0,i<0?0:i+delta))].id; }
export function tradeAtTime(executions:{time:number;trade_id:string}[],time:number):string|null{return executions.find(e=>e.time===time)?.trade_id??null;}
