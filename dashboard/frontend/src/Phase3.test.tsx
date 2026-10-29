// @vitest-environment jsdom
import {it,expect,vi,afterEach} from 'vitest';
import {render,screen,cleanup,waitFor,act,within} from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import App from './App';
import {Phase3} from './Phase3';
import type {Overview} from './types';
const collections=['sources','cards','gaps','hypotheses','queue','lessons','cycles'];
const snapshot=()=>({available:true,integrity:{verified:true,event_count:7,head_hash:'a'.repeat(64)},counts:Object.fromEntries(collections.map(k=>[k,1])),safety:{execution_enabled:false,scheduler_enabled:false,credentials_enabled:false},sources:[{id:'SYNTHETIC source',version:1,status:'VERIFIED_METADATA_PENDING_HUMAN_APPROVAL',url:'javascript:alert(1)'}],cards:[{id:'SYNTHETIC card',version:2,claim:'<img src=x onerror=alert(1)>',uncertainties:['SYNTHETIC uncertain']}],gaps:[{id:'SYNTHETIC gap',question:'SYNTHETIC question'}],hypotheses:[{id:'SYNTHETIC hypothesis',family:'momentum',rank_score:12}],queue:[{id:'SYNTHETIC proposal',status:'PROPOSED',plan:{engine_evaluations_consumed:0}}],lessons:[{id:'SYNTHETIC lesson'}],cycles:[{id:'SYNTHETIC cycle',status:'RUNNING',critic:{verdict:'REVISE',issues:['SYNTHETIC critic issue']},progress:{stage:'critic',model_calls:3}}]});
it('shows versioned knowledge, four families, proposal-only queue, progress, critics and disabled gates safely',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(snapshot()))));
 const {container}=render(<Phase3 overview={overview as unknown as Overview}/>);
 expect(await screen.findByText('Phase3 · ตรวจสอบสายเหตุการณ์แล้ว')).toBeInTheDocument();
 for(const heading of ['ความก้าวหน้ารอบวิจัย / Critic audit','ฐานความรู้แบบมีเวอร์ชัน','แค็ตตาล็อกแหล่งข้อมูล · รอมนุษย์ตรวจ','สมมติฐานสี่ตระกูล','คิวข้อเสนอ · ไม่ใช่ผลทดลอง','บทเรียน','ช่องว่างความรู้'])expect(screen.getByRole('heading',{name:heading})).toBeInTheDocument();
 for(const family of ['trend_following','momentum','mean_reversion','volatility'])expect(screen.getByRole('heading',{name:family})).toBeInTheDocument();
 expect(screen.getByText(/heuristic ไม่ใช่กำไรคาดหวัง/)).toBeInTheDocument();
 expect(screen.getByText(/SYNTHETIC critic issue/)).toBeInTheDocument();
 expect(screen.getByText('VERIFIED_METADATA_PENDING_HUMAN_APPROVAL',{selector:'.phase3-record-status'})).toBeVisible();
 expect(screen.getByText(/onerror=alert/)).toBeInTheDocument();
 expect(container.querySelector('img,iframe,script,a')).toBeNull();
 expect(screen.getByText(/execution_enabled: false/)).toBeInTheDocument();
 expect(screen.getByText(/scheduler_enabled: false/)).toBeInTheDocument();
 expect(screen.getByText(/v2/)).toBeInTheDocument();
 expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
it('shows only typed optional summary fields and preserves unknown nested content as text',async()=>{
 const data=snapshot();data.hypotheses=[{id:'SYNTHETIC hypothesis',family:'momentum',rank_score:12,score:18,title_th:'SYNTHETIC Thai title',status:'PROPOSED'} as typeof data.hypotheses[number]];
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(data))));
 render(<Phase3 overview={overview as unknown as Overview}/>);
 expect(await screen.findByRole('heading',{name:'SYNTHETIC Thai title'})).toBeInTheDocument();
 expect(screen.getByText('Heuristic score: 18')).toBeInTheDocument();
 expect(screen.getAllByText('PROPOSED',{selector:'.phase3-record-status'})).toHaveLength(2);
});

it('renders hostile non-string optional fields generically without coercion or crashes',async()=>{
 const data=snapshot();
 Object.assign(data.hypotheses[0],{family:{toString:{payload:'SYNTHETIC untrusted family'}},title_th:{html:'SYNTHETIC title data'},score:{value:99},status:['SYNTHETIC nested status']});
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(data))));
 render(<Phase3 overview={overview as unknown as Overview}/>);
 expect(await screen.findByRole('heading',{name:'สมมติฐานที่ยังไม่จัดตระกูล'})).toBeInTheDocument();
 const record=screen.getByRole('heading',{name:'SYNTHETIC hypothesis'}).closest('article')!;
 fireEvent.click(within(record).getByText('ดูข้อมูลดิบ JSON · ตรวจสอบย้อนกลับ'));
 expect(await within(record).findByText(/SYNTHETIC untrusted family/,{selector:'pre'})).toBeInTheDocument();
 expect(screen.queryByText(/Heuristic score:/)).not.toBeInTheDocument();
});

it.each([
 ['unverified',()=>({...snapshot(),integrity:{verified:false,event_count:7,head_hash:'a'.repeat(64)}})],
 ['unsafe safety',()=>({...snapshot(),safety:{execution_enabled:true,scheduler_enabled:false,credentials_enabled:false}})],
 ['bad count',()=>({...snapshot(),counts:{...snapshot().counts,cards:99}})],
 ['null record',()=>({...snapshot(),cards:[null]})],
 ['missing collection',()=>({...snapshot(),cycles:undefined})],
 ['false absence',()=>({...snapshot(),available:false})],
])('fails closed without a verified label on malformed %s',async(_name,make)=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(make()))));
 render(<Phase3 overview={overview as unknown as Overview}/>);
 expect(await screen.findByRole('alert')).toHaveTextContent('Phase3');
 expect(screen.queryByText('Phase3 · ตรวจสอบสายเหตุการณ์แล้ว')).not.toBeInTheDocument();
 expect(screen.queryByText('SYNTHETIC card')).not.toBeInTheDocument();
});

it('clears stale verified research on refresh failure and ignores an older response racing it',async()=>{
 let resolveOld:(r:Response)=>void=()=>{};
 const fetcher=vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(snapshot()))).mockImplementationOnce(()=>new Promise<Response>(resolve=>{resolveOld=resolve;})).mockResolvedValueOnce(new Response(JSON.stringify({detail:{message_th:'SYNTHETIC corrupt Phase3'}}),{status:503}));
 vi.stubGlobal('fetch',fetcher);
 render(<Phase3 overview={overview as unknown as Overview}/>);
 await screen.findByText('SYNTHETIC card');
 fireEvent.focus(window);
 await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(2));
 expect(screen.queryByText('SYNTHETIC card')).not.toBeInTheDocument();
 fireEvent.focus(window);
 await screen.findByRole('alert');
 await act(async()=>{resolveOld(new Response(JSON.stringify(snapshot())));});
 expect(screen.getByRole('alert')).toHaveTextContent('SYNTHETIC corrupt Phase3');
 expect(screen.queryByText('Phase3 · ตรวจสอบสายเหตุการณ์แล้ว')).not.toBeInTheDocument();
 expect(screen.getByText(/Batch001 · หลักฐานเดิมแยกจากข้อเสนอ Phase3/)).toBeInTheDocument();
 expect(fetcher.mock.calls.every(([url,options])=>url==='/api/phase3'&&options.method==='GET')).toBe(true);
});

import {fireEvent} from '@testing-library/react';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
// SYNTHETIC responses only; not production research results.
const overview={batch_id:'SYNTHETIC',integrity:{verified:true,engine_evaluations:20,event_count:88},strategies:[]};
it('shows persisted cycle details rankings in their recorded order without recalculating scores',async()=>{
 const data=snapshot();
 Object.assign(data.cycles[0],{details:{rankings:[
  {id:'SYNTHETIC ranked B',title_th:'อันดับบันทึก B',score:7,scores:{evidence_quality:5}},
  {id:'SYNTHETIC ranked A',title_th:'อันดับบันทึก A',score:19},
 ],score_meaning:'SYNTHETIC ordinal planning only'}});
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(data))));
 render(<Phase3 overview={overview as unknown as Overview}/>);
 const ranking=await screen.findByRole('region',{name:'อันดับสมมติฐานที่บันทึก · SYNTHETIC cycle'});
 const rows=within(ranking).getAllByRole('listitem');
 expect(rows).toHaveLength(2);
 expect(rows[0]).toHaveTextContent('อันดับ 1');expect(rows[0]).toHaveTextContent('อันดับบันทึก B');expect(rows[0]).toHaveTextContent('Heuristic score: 7');
 expect(rows[1]).toHaveTextContent('อันดับ 2');expect(rows[1]).toHaveTextContent('อันดับบันทึก A');expect(rows[1]).toHaveTextContent('Heuristic score: 19');
 expect(within(ranking).getByText(/heuristic ไม่ใช่ผลตอบแทน/)).toBeInTheDocument();
 expect(within(ranking).getByText('SYNTHETIC ordinal planning only')).toBeInTheDocument();
});

it('presents Thai evidence summaries and truthful gates while large raw snapshots stay collapsed',async()=>{
 const data=snapshot();
 Object.assign(data.cards[0],{claim_th:'ข้ออ้างที่จำกัดขอบเขต',uncertainties_th:['ยังไม่มีหลักฐาน alpha'],source_bindings:[{source_id:'SYNTHETIC source',binding_hash:'binding-hash'}],citations:[{locator:'บทที่ 1'}]});
 Object.assign(data.hypotheses[0],{hypothesis_th:'ทดสอบสมมติฐานเท่านั้น',entry_logic:'เข้าหลังแท่งปิด',exit_logic:'ออกเมื่อสัญญาณกลับ',falsification:'หักล้างเมื่อไม่ผ่านเกณฑ์',parameters:{lookback:20}});
 Object.assign(data.queue[0],{human_approved:false,approval_scope:'DESIGN_ONLY',plan_hash:'plan-hash',plan:{status:'DESIGN_ONLY',costs:{commission:0.001,spread:0.0005,kind:'scenario_not_verified_exchange_costs'},data_status:'UNAVAILABLE_UNVERIFIED',windows:{development:{start:'SYNTHETIC start',end:'SYNTHETIC end'}},budget:{approved:false,max_evaluations:10},engine_evaluations_consumed:0}});
 Object.assign(data.sources[0],{title:'เอกสารรอตรวจ',doi:'10.synthetic/document',status:'QUARANTINED_DOCUMENT_TEXT',approved:false,raw_sha256:'raw-hash',text_sha256:'text-hash',review_history:[{reviewer:'ผู้ตรวจจำลอง',reason:'รอตรวจขอบเขต'}],raw_snapshot:'<html>HUGE SYNTHETIC RAW SNAPSHOT</html>'});
 Object.assign(data.cycles[0],{details:{critic:{verdict:'REVISE',issues:['ต้องตรวจเอกสารก่อน']},engine_evaluations_consumed:0}});
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(data))));
 const {container}=render(<Phase3 overview={overview as unknown as Overview}/>);
 await screen.findByText('Phase3 · ตรวจสอบสายเหตุการณ์แล้ว');
 const card=screen.getByRole('heading',{name:'SYNTHETIC card'}).closest('article')!;
 const hypothesis=screen.getByRole('heading',{name:'SYNTHETIC hypothesis'}).closest('article')!;
 const queue=screen.getByRole('heading',{name:'SYNTHETIC proposal'}).closest('article')!;
 const source=screen.getByRole('heading',{name:'เอกสารรอตรวจ'}).closest('article')!;
 expect(within(card).getByText('ข้ออ้างที่จำกัดขอบเขต')).toBeVisible();expect(within(card).getByText('ยังไม่มีหลักฐาน alpha')).toBeVisible();
 expect(within(card).getByText('binding-hash')).toBeVisible();expect(within(card).getByText('บทที่ 1')).toBeVisible();
 for(const text of ['เงื่อนไขเข้า','เงื่อนไขออก','เกณฑ์หักล้าง','พารามิเตอร์','เข้าหลังแท่งปิด','ออกเมื่อสัญญาณกลับ','หักล้างเมื่อไม่ผ่านเกณฑ์','lookback','20'])expect(within(hypothesis).getByText(text)).toBeVisible();
 for(const text of ['การอนุมัติแผนโดยมนุษย์','ยังเป็นข้อเสนอ — ยังไม่อนุมัติ','ต้นทุนสมมติ','ความพร้อมข้อมูล','UNAVAILABLE_UNVERIFIED','commission','0.001','spread','0.0005','plan-hash'])expect(within(queue).getByText(text)).toBeVisible();
 for(const text of ['กักกันข้อความเอกสาร — ยังไม่อนุมัติให้ใช้เป็นหลักฐาน','10.synthetic/document','raw-hash','text-hash','ผู้ตรวจจำลอง'])expect(within(source).getByText(text)).toBeVisible();
 expect(screen.getByText('ต้องตรวจเอกสารก่อน')).toBeVisible();
 expect(container.querySelectorAll('pre')).toHaveLength(0);
 const raw=source.querySelector('details')!;expect(raw.open).toBe(false);
 fireEvent.click(within(source).getByText('ดูข้อมูลดิบ JSON · ตรวจสอบย้อนกลับ'));
 expect(raw.open).toBe(true);expect(await within(source).findByText(/HUGE SYNTHETIC RAW SNAPSHOT/,{selector:'pre'})).toBeInTheDocument();
 expect(container.querySelector('img,iframe,script,a')).toBeNull();
});

it('exposes metadata provenance and reviewed-document receipts without treating legacy seeds as new approvals',async()=>{
 const data=snapshot();
 Object.assign(data.sources[0],{title:'เอกสารที่ตรวจแล้ว',status:'APPROVED_REVIEWED_DOCUMENT',approved:true,requested_url:'SYNTHETIC request',final_url:'SYNTHETIC final',approval:{reviewer:'SYNTHETIC receipt reviewer',scope:'full-document',source_version:2},verification:{raw_sha256:'SYNTHETIC metadata hash',retrieved_at:'SYNTHETIC retrieval',raw_snapshot:'SYNTHETIC hidden metadata snapshot'}});
 Object.assign(data.queue[0],{status:'APPROVED',human_approved:true,approval_scope:'DESIGN_ONLY'});
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(data))));
 render(<Phase3 overview={overview as unknown as Overview}/>);
 const source=(await screen.findByRole('heading',{name:'เอกสารที่ตรวจแล้ว'})).closest('article')!;
 for(const text of ['สถานะระบุว่าเอกสารผ่านการตรวจโดยมนุษย์ — ไม่ใช่การยืนยัน alpha','SYNTHETIC receipt reviewer','full-document','SYNTHETIC metadata hash','SYNTHETIC retrieval','SYNTHETIC request','SYNTHETIC final'])expect(within(source).getByText(text)).toBeVisible();
 expect(screen.queryByText(/SYNTHETIC hidden metadata snapshot/)).not.toBeInTheDocument();
 expect(screen.getByText('สถานะอนุมัติแผน DESIGN_ONLY — ไม่ใช่สิทธิ์รัน')).toBeVisible();
 expect(screen.queryByRole('button')).not.toBeInTheDocument();
});

it.each([null,{},[],[null,{id:'SYNTHETIC malformed ranking',score:{unsafe:99},title_th:['not a title']}]].map(rankings=>({rankings})))('does not invent scores or use top-level rankings when cycle details rankings are $rankings',async({rankings})=>{
 const data=snapshot();Object.assign(data.cycles[0],{rankings:[{id:'SYNTHETIC ignored top-level',score:900}],details:{rankings}});
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(data))));
 render(<Phase3 overview={overview as unknown as Overview}/>);
 const ranking=await screen.findByRole('region',{name:'อันดับสมมติฐานที่บันทึก · SYNTHETIC cycle'});
 expect(within(ranking).queryByText(/Heuristic score:/)).not.toBeInTheDocument();
 expect(within(ranking).queryByText(/SYNTHETIC ignored top-level/)).not.toBeInTheDocument();
 if(!Array.isArray(rankings)||!rankings.length)expect(within(ranking).getByText(/ยังไม่มีอันดับที่บันทึกในรอบนี้/)).toBeVisible();
});

it('does not poll a hidden tab and refreshes when visible again',async()=>{
 let visibility='hidden';vi.spyOn(document,'visibilityState','get').mockImplementation(()=>visibility as DocumentVisibilityState);
 const fetcher=vi.fn(async()=>new Response(JSON.stringify(snapshot())));vi.stubGlobal('fetch',fetcher);
 render(<Phase3 overview={overview as unknown as Overview}/>);
 fireEvent.focus(window);expect(fetcher).not.toHaveBeenCalled();
 visibility='visible';fireEvent(document,new Event('visibilitychange'));
 expect(await screen.findByText('Phase3 · ตรวจสอบสายเหตุการณ์แล้ว')).toBeInTheDocument();expect(fetcher).toHaveBeenCalledTimes(1);
 vi.restoreAllMocks();
});

it('opens an independent read-only Thai Phase3 tab and keeps Batch001 when state is absent',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:unknown)=>new Response(JSON.stringify(String(url).endsWith('/overview')?overview:{available:false,integrity:{verified:false,event_count:0,head_hash:null},counts:Object.fromEntries(['sources','cards','gaps','hypotheses','queue','lessons','cycles'].map(k=>[k,0])),sources:[],cards:[],gaps:[],hypotheses:[],queue:[],lessons:[],cycles:[],safety:{execution_enabled:false,scheduler_enabled:false,credentials_enabled:false}}))));
 render(<App/>);
 fireEvent.click(screen.getByRole('button',{name:'วิจัยอัตโนมัติ · Phase3'}));
 expect(await screen.findByText('ยังไม่มีสถานะ Phase3 — ไม่สร้างฐานข้อมูลจากหน้านี้')).toBeInTheDocument();
 expect(screen.getByText(/Batch001 · หลักฐานเดิมแยกจากข้อเสนอ Phase3/)).toBeInTheDocument();
 expect(screen.getAllByRole('button').filter(b=>/^(อนุมัติ|เริ่มรัน|Run|Approve)$/i.test(b.textContent??''))).toHaveLength(0);
});
