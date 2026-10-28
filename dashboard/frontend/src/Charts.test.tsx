import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {MarketChart,PortfolioCharts} from './Charts';
import type {View} from './types';

// Explicitly synthetic layout-only fixture; no market data or strategy execution.
const view={strategy:{fast:10,slow:50},scope:{start_utc:'2020-01-01T00:00:00Z',end_exclusive_utc:'2020-01-02T00:00:00Z'},candles:[],executions:[],equity:[]} as unknown as View;

describe('autosized chart container regression',()=>{
  it('constrains the market host height independently of chart children',()=>{
    const html=renderToStaticMarkup(<MarketChart view={view} selected={null} onSelect={()=>{}}/>);
    expect(html).toContain('height:390px');
  });
  it('constrains both equity and drawdown host heights',()=>{
    const html=renderToStaticMarkup(<PortfolioCharts view={view}/>);
    expect(html).toContain('height:330px');
    expect(html).toContain('height:160px');
  });
});
