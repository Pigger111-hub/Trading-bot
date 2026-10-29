import {useEffect,useState} from 'react';
import {get} from './api';
import './phase3.css';
import type {Overview,Phase3Item,Phase3Snapshot} from './types';

const collections=['sources','cards','gaps','hypotheses','queue','lessons','cycles'] as const;
function object(value:unknown):value is Record<string,unknown>{return value!==null&&typeof value==='object'&&!Array.isArray(value);}
function validJSON(value:unknown,depth=0):boolean{
 if(depth>50)return false;
 if(value===null||typeof value==='string'||typeof value==='boolean')return true;
 if(typeof value==='number')return Number.isFinite(value);
 if(Array.isArray(value))return value.every(v=>validJSON(v,depth+1));
 return object(value)&&Object.values(value).every(v=>validJSON(v,depth+1));
}
function snapshot(value:unknown):Phase3Snapshot{
 const invalid=()=>{throw new Error('Phase3 รูปแบบหรือสถานะความปลอดภัยไม่ผ่านการตรวจสอบ');};
 if(!object(value)||typeof value.available!=='boolean'||!object(value.integrity)||!object(value.counts)||!object(value.safety))return invalid();
 const {integrity,counts,safety}=value;
 if(!Number.isSafeInteger(integrity.event_count)||Number(integrity.event_count)<0||integrity.verified!==value.available)return invalid();
 if(integrity.event_count===0?integrity.head_hash!==null:typeof integrity.head_hash!=='string'||!/^[a-f0-9]{64}$/.test(integrity.head_hash))return invalid();
 for(const key of ['execution_enabled','scheduler_enabled','credentials_enabled'])if(safety[key]!==false)return invalid();
 for(const key of collections){const items=value[key];
  if(!Array.isArray(items)||!Number.isSafeInteger(counts[key])||counts[key]!==items.length||(!value.available&&items.length!==0))return invalid();
  if(!items.every(item=>object(item)&&typeof item.id==='string'&&item.id.trim()&&validJSON(item)))return invalid();
 }
 if(!value.available&&integrity.event_count!==0)return invalid();
 return value as Phase3Snapshot;
}

function Rankings({cycle}:{cycle:Phase3Item}){
 const details=object(cycle.details)?cycle.details:null;
 const rankings=details?.rankings;
 return <section className="phase3-rankings" aria-label={`อันดับสมมติฐานที่บันทึก · ${cycle.id}`}><h4>อันดับสมมติฐานที่บันทึก</h4><p>ลำดับจาก cycles.details.rankings · heuristic ไม่ใช่ผลตอบแทน กำไรคาดหวัง หรือ mutual information ที่คำนวณจริง · ไม่คำนวณคะแนนใหม่ในหน้านี้</p>{typeof details?.score_meaning==='string'&&<p>{details.score_meaning}</p>}{Array.isArray(rankings)&&rankings.length?<ol>{rankings.map((row,index)=><li key={index}><strong>อันดับ {index+1} · {object(row)&&typeof row.title_th==='string'?row.title_th:object(row)&&typeof row.id==='string'?row.id:'ไม่ระบุชื่อสมมติฐาน'}</strong><p>{object(row)&&typeof row.score==='number'?`Heuristic score: ${row.score}`:'ไม่มีคะแนนที่บันทึก'}</p></li>)}</ol>:<p className="muted">ยังไม่มีอันดับที่บันทึกในรอบนี้ — ไม่จัดอันดับทดแทนจากสมมติฐาน</p>}</section>;
}
type Kind=typeof collections[number];
const missing='ไม่มีข้อมูลที่บันทึก';
const labels:Record<string,string>={verdict:'ข้อสรุป Critic',issues:'ประเด็นที่ต้องแก้',lessons_th:'บทเรียน',next_questions:'คำถามถัดไป',reviewer:'ผู้ตรวจ',actor:'ผู้ดำเนินการ',reason:'เหตุผล',at:'เวลาที่ตรวจ',scope:'ขอบเขต',source_id:'รหัสแหล่งอ้างอิง',quote:'ข้อความอ้างอิง',start:'เริ่ม UTC',end:'สิ้นสุด UTC',development:'พัฒนา',validation:'ตรวจสอบ',holdout:'ชุดกันไว้',approved:'อนุมัติตามบันทึก',max_evaluations:'เพดานการประเมิน',max_configs:'เพดานรูปแบบ',stage:'ขั้นตอน',model_calls:'การเรียกโมเดล',evidence_quality:'คุณภาพหลักฐาน',novelty:'ความใหม่เทียบประวัติ',information_gain:'ประโยชน์ข้อมูลแบบ heuristic',complexity:'ความซับซ้อน'};
// Render saved JSON as React text only; never coerce unknown objects to strings.
function Readable({value}:{value:unknown}){
 if(value===null||value===undefined)return <span className="muted">{missing}</span>;
 if(typeof value==='string'||typeof value==='number')return <span>{value}</span>;
 if(typeof value==='boolean')return <span>{value?'ใช่ (true)':'ไม่ใช่ (false)'}</span>;
 if(Array.isArray(value))return value.length?<ul className="phase3-list">{value.map((v,i)=><li key={i}><Readable value={v}/></li>)}</ul>:<span className="muted">ไม่มีรายการที่บันทึก</span>;
 if(object(value))return Object.keys(value).length?<dl className="phase3-fields">{Object.entries(value).map(([k,v])=><div key={k}><dt>{Object.prototype.hasOwnProperty.call(labels,k)?labels[k]:k}</dt><dd><Readable value={v}/></dd></div>)}</dl>:<span className="muted">ไม่มีค่าที่บันทึก</span>;
 return <span className="muted">{missing}</span>;
}
function Fields({item,fields}:{item:Record<string,unknown>;fields:[string,string][]}){
 return <dl className="phase3-fields">{fields.map(([key,label])=><div key={key}><dt>{label}</dt><dd><Readable value={item[key]}/></dd></div>)}</dl>;
}
function Critic({value}:{value:unknown}){
 return <section className="phase3-critic"><h4>คำวิจารณ์อิสระ</h4>{object(value)?<Fields item={value} fields={[['verdict','ข้อสรุป Critic'],['issues','ประเด็นที่ต้องแก้'],['lessons_th','บทเรียน'],['next_questions','คำถามถัดไป']]}/>:<p className="muted">ยังไม่มีคำวิจารณ์ที่บันทึก</p>}<p className="muted">ACCEPT_AS_PROPOSAL รับเป็นข้อเสนอเท่านั้น ไม่ใช่อนุมัติโดยมนุษย์หรือสิทธิ์รัน</p></section>;
}
function RawRecord({item}:{item:Phase3Item}){
 const [open,setOpen]=useState(false);
 return <details className="phase3-raw" onToggle={e=>setOpen(e.currentTarget.open)}><summary>ดูข้อมูลดิบ JSON · ตรวจสอบย้อนกลับ</summary>{open&&<pre>{JSON.stringify(item,null,2)}</pre>}</details>;
}
function Summary({item,kind}:{item:Phase3Item;kind?:Kind}){
 const details=object(item.details)?item.details:{};
 const plan=object(item.plan)?item.plan:{};
 if(kind==='cycles')return <><Fields item={object(item.progress)?item.progress:{}} fields={[['stage','ขั้นตอนที่บันทึก'],['model_calls','การเรียกโมเดลที่บันทึก']]}/><Fields item={details} fields={[['candidate_count','แหล่งข้อมูลค้นพบ'],['seed_count','เอกสารในรอบ'],['cards_count','การ์ดในรอบ'],['engine_evaluations_consumed','การประเมิน engine ที่ใช้'],['error','ข้อผิดพลาดที่บันทึก']]}/><Rankings cycle={item}/><Critic value={details.critic??item.critic}/></>;
 if(kind==='cards')return <><Fields item={item} fields={[[typeof item.claim_th==='string'?'claim_th':'claim','ข้ออ้างตามหลักฐาน'],[Array.isArray(item.uncertainties_th)?'uncertainties_th':'uncertainties','ข้อจำกัด / สิ่งที่ยังไม่รู้'],['evidence_scope','ขอบเขตหลักฐาน'],['quotes','ข้อความอ้างอิง'],['source_bindings','การผูกหลักฐานกับแหล่งข้อมูล'],['citations','ตำแหน่งอ้างอิง']]}/>{item.critic!==undefined&&<Critic value={item.critic}/>}</>;
 if(kind==='sources'){
  const notice=item.status==='QUARANTINED_DOCUMENT_TEXT'?'กักกันข้อความเอกสาร — ยังไม่อนุมัติให้ใช้เป็นหลักฐาน':item.status==='APPROVED_REVIEWED_DOCUMENT'?'สถานะระบุว่าเอกสารผ่านการตรวจโดยมนุษย์ — ไม่ใช่การยืนยัน alpha':item.status==='VERIFIED_METADATA_PENDING_HUMAN_APPROVAL'?'ตรวจ metadata แล้ว — ยังรอมนุษย์อนุมัติ ไม่ใช่หลักฐานเนื้อหาเอกสาร':'แสดงสถานะตามบันทึกเท่านั้น — ไม่อนุมานการอนุมัติจากชื่อหรือ URL';
  return <><p className="phase3-notice">{notice}</p><Fields item={item} fields={[['doi','DOI'],['url','URL (ข้อความเท่านั้น)'],['requested_url','URL ที่ร้องขอ (ข้อความเท่านั้น)'],['final_url','URL สุดท้าย (ข้อความเท่านั้น)'],['evidence_scope','ขอบเขตหลักฐาน'],['support_scope','ขอบเขตข้ออ้างที่รองรับ'],['approved','อนุมัติตามบันทึก'],['retrieved_at','เวลาที่ดึงเอกสาร'],['raw_sha256','SHA256 เอกสารดิบ'],['text_sha256','SHA256 ข้อความ'],['approval','ใบรับรองการตรวจตามบันทึก'],['review_history','ผู้ตรวจและประวัติการตรวจ']]}/>{object(item.verification)&&<Fields item={item.verification} fields={[['authority','ผู้ให้ metadata'],['retrieved_at','เวลาที่ดึง metadata'],['raw_sha256','SHA256 metadata ดิบ']]}/>}</>;
 }
 if(kind==='hypotheses')return <Fields item={item} fields={[['hypothesis_th','สมมติฐานที่ต้องทดสอบ'],['entry_logic','เงื่อนไขเข้า'],['exit_logic','เงื่อนไขออก'],['falsification','เกณฑ์หักล้าง'],['parameters','พารามิเตอร์'],['source_ids','แหล่งอ้างอิง'],['scores','องค์ประกอบคะแนน heuristic ที่บันทึก']]}/>;
 if(kind==='queue')return <><p className="phase3-notice">{item.status==='PROPOSED'?'ยังเป็นข้อเสนอ — ยังไม่อนุมัติ':item.status==='APPROVED'?'สถานะอนุมัติแผน DESIGN_ONLY — ไม่ใช่สิทธิ์รัน':item.status==='REJECTED'?'ข้อเสนอไม่ผ่าน — ไม่ใช่ผลทดลอง':'สถานะตามบันทึก — ไม่อนุมานว่าทดลองเสร็จแล้ว'}</p><Fields item={item} fields={[['hypothesis_id','รหัสสมมติฐาน'],['human_approved','การอนุมัติแผนโดยมนุษย์'],['approval_scope','ขอบเขตการอนุมัติ'],['approval','หลักฐานการอนุมัติ'],['review_history','ประวัติการตรวจ'],['plan_hash','Hash แผน'],['engine_evaluations_consumed','การประเมิน engine ที่ใช้']]}/><h4>แผนที่เสนอ · ยังไม่ใช่ผลทดลอง</h4><Fields item={plan} fields={[['status','สถานะแผน'],['market','ตลาดที่เสนอ'],['capital','เงินทุนสมมติ'],['costs','ต้นทุนสมมติ'],['cost_sensitivity','สถานการณ์ต้นทุนที่สูงขึ้น'],['data_status','ความพร้อมข้อมูล'],['freshness_note','ข้อจำกัดด้านข้อมูลใหม่'],['windows','ช่วงข้อมูลที่เสนอ'],['split_method','วิธีแบ่งข้อมูล'],['method','วิธีทดสอบที่เสนอ'],['budget','งบที่เสนอ'],['budget_accounting','บัญชีงบประมาณ'],['gates','ประตูอนุญาตตามบันทึก']]}/><p className="muted">วันในแผนไม่ยืนยันว่ามีข้อมูลพร้อมใช้ · ต้นทุนเป็น scenario ไม่ใช่ค่าธรรมเนียมตลาดที่ตรวจแล้ว</p><Critic value={item.critic}/></>;
 return <Fields item={item} fields={kind==='gaps'?[[typeof item.question_th==='string'?'question_th':'question','คำถามที่ยังไม่คลี่คลาย']]:[['text_th','บทเรียนตามบันทึก'],['critic_verdict','ข้อสรุป Critic']]}/>;
}
function Records({items,kind}:{items:Phase3Item[];kind?:Kind}){
 return items.length?<div className="phase3-records">{items.map((item,index)=><article className="research-item" key={typeof item.id==='string'?item.id:index}><h3>{typeof item.title_th==='string'?item.title_th:typeof item.title==='string'?item.title:typeof item.id==='string'?item.id:'บันทึก'}</h3><div className="phase3-record-meta">{typeof item.version==='number'&&<span className="badge">v{item.version}</span>}{typeof item.status==='string'&&<span className="badge phase3-record-status">{item.status}</span>}{typeof item.score==='number'&&<span className="badge">Heuristic score: {item.score}</span>}</div><Summary item={item} kind={kind}/><RawRecord item={item}/></article>)}</div>:<p className="muted">ยังไม่มีบันทึก — ไม่เติมข้อมูลตัวอย่าง</p>;
}
function Block({title,items,kind}:{title:string;items:Phase3Item[];kind?:typeof collections[number]}){return <section className="panel padded"><h2>{title}</h2><Records items={items} kind={kind}/></section>;}
export function Phase3({overview}:{overview:Overview}){
 const [data,setData]=useState<Phase3Snapshot|null>(null);
 const [error,setError]=useState<string|null>(null);
 useEffect(()=>{let active=true,sequence=0;let controller:AbortController;
  const load=()=>{if(document.visibilityState==='hidden')return;
   controller?.abort();controller=new AbortController();const request=++sequence;
   setData(null);setError(null);
   get<unknown>('/phase3',controller.signal).then(snapshot).then(value=>{if(active&&request===sequence)setData(value);}).catch(e=>{if(active&&request===sequence){setData(null);setError(e instanceof Error?e.message:'อ่าน Phase3 ไม่สำเร็จ');}});
  };
  load();const interval=window.setInterval(load,30000);window.addEventListener('focus',load);document.addEventListener('visibilitychange',load);
  return()=>{active=false;sequence++;controller?.abort();clearInterval(interval);window.removeEventListener('focus',load);document.removeEventListener('visibilitychange',load);};
 },[]);
 return <div className="phase3"><section className="panel padded"><h2>Batch001 · หลักฐานเดิมแยกจากข้อเสนอ Phase3</h2><p>การประเมิน engine ที่บันทึกจริง {overview.integrity.engine_evaluations} · events {overview.integrity.event_count}</p><p>ผลเสร็จแล้วใน Batch001 ไม่ใช่การทดลองจากคิว Phase3 · ประวัติจริงอยู่ในแท็บห้องวิจัยเดิม</p></section>
 {error?<div className="error-panel" role="alert">{error}<p>Phase3 UNVERIFIED · ไม่แสดงข้อมูลเก่าทดแทน หลักฐาน Batch001 ด้านบนเป็นคนละชุด</p></div>:!data?<p role="status">กำลังตรวจสอบ Phase3…</p>:<>
 <section className="panel padded"><h2>{data.available?'Phase3 · ตรวจสอบสายเหตุการณ์แล้ว':'ยังไม่มีสถานะ Phase3 — ไม่สร้างฐานข้อมูลจากหน้านี้'}</h2><p>การตรวจสอบ hash ยืนยันความครบถ้วนของบันทึก ไม่ได้ยืนยันข้ออ้างงานวิจัย</p><p className="mono">events {data.integrity.event_count} · head {data.integrity.head_hash??'ไม่มี'}</p><div className="phase3-counts">{Object.entries(data.counts).map(([name,count])=><span className="badge" key={name}>{name}: {count}</span>)}</div><p>นับเอกสารเวอร์ชันล่าสุด ไม่ใช่จำนวนผลทดลองสำเร็จ</p><p className="mono">execution_enabled: false · scheduler_enabled: false · credentials_enabled: false</p><p>การอนุมัติเป็น DESIGN_ONLY โดยมนุษย์เท่านั้น ไม่ใช่สิทธิ์รัน · ไม่มี auto-approval / model / engine / backtest / scheduler จากแดชบอร์ด</p><p>Phase3 เป็นการวิจัยและวางแผนเท่านั้น ไม่มีผลทดลองใหม่จากคิวนี้</p></section>
 <Block title="ความก้าวหน้ารอบวิจัย / Critic audit" items={data.cycles} kind="cycles"/>
 <p className="muted">COMPLETED ใน cycles หมายถึงจบรอบวิจัย ไม่ใช่ backtest สำเร็จ · แสดงสถานะ/ขั้นตอน/คำวิจารณ์ตามบันทึกเท่านั้น ไม่คาดเดาเปอร์เซ็นต์</p>
 <div className="research-grid"><Block title="ฐานความรู้แบบมีเวอร์ชัน" items={data.cards} kind="cards"/><Block title="แค็ตตาล็อกแหล่งข้อมูล · รอมนุษย์ตรวจ" items={data.sources} kind="sources"/></div>
 <p className="muted">VERIFIED_METADATA_PENDING_HUMAN_APPROVAL คือ metadata ที่รออนุมัติ ไม่ใช่หลักฐาน full text หรือความน่าเชื่อถือทางวิทยาศาสตร์ · URL เป็นข้อความเท่านั้น ไม่มีการดึงข้อมูลภายนอก</p>
 <section className="panel padded"><h2>สมมติฐานสี่ตระกูล</h2><p>อันดับ/คะแนนที่บันทึกเป็น heuristic ไม่ใช่กำไรคาดหวัง หรือ mutual information ที่คำนวณจริง · 3×evidence_quality + 2×novelty + 3×information_gain − 2×complexity</p><div className="research-grid">{['trend_following','momentum','mean_reversion','volatility'].map(family=><section key={family}><h3>{family}</h3><Records items={data.hypotheses.filter(h=>h.family===family)} kind="hypotheses"/></section>)}</div>{data.hypotheses.some(h=>(typeof h.family!=='string'||!['trend_following','momentum','mean_reversion','volatility'].includes(h.family)))&&<Block title="สมมติฐานที่ยังไม่จัดตระกูล" items={data.hypotheses.filter(h=>(typeof h.family!=='string'||!['trend_following','momentum','mean_reversion','volatility'].includes(h.family)))} kind="hypotheses"/>}</section>
 <Block title="คิวข้อเสนอ · ไม่ใช่ผลทดลอง" items={data.queue} kind="queue"/><p className="muted">PROPOSED = ยังไม่อนุมัติ · APPROVED = DESIGN_ONLY · REJECTED = ไม่ผ่าน · ค่าตัวเลขและสถานะในเอกสารเป็นข้อเสนอ ไม่ใช่ผลกำไรที่ทดลองแล้ว</p>
 <div className="research-grid"><Block title="บทเรียน" items={data.lessons} kind="lessons"/><Block title="ช่องว่างความรู้" items={data.gaps} kind="gaps"/></div>
 </>}</div>;
}
