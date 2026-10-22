"use strict";
const {test}=require("node:test"),assert=require("node:assert/strict");
const {readFileSync,existsSync}=require("node:fs"),{resolve}=require("node:path"),{spawnSync}=require("node:child_process"),{JSDOM}=require("jsdom");
const root=resolve(__dirname,"../.."),python=existsSync(resolve(root,".venv/bin/python"))?resolve(root,".venv/bin/python"):"python";
const fixture=spawnSync(python,[resolve(__dirname,"oneclick_fixture.py")],{cwd:root,encoding:"utf8",timeout:30000});
assert.equal(fixture.status,0,`Install locked Python test dependencies first. One-click ASGI fixture failed: ${fixture.stderr}`);
const original=JSON.parse(fixture.stdout),key=original["qa/completed"].problem_id;
const html=readFileSync(resolve(root,"vision/static/index.html"),"utf8");
const scripts=["investigate.js","home.js","app.js"].map(n=>readFileSync(resolve(root,"vision/static/"+n),"utf8")).join("\n");
const response=value=>({ok:true,json:async()=>structuredClone(value)});
async function until(predicate){const deadline=performance.now()+3000;while(!predicate()){if(performance.now()>deadline)assert.fail("Whole-app one-click DOM did not reach expected state");await new Promise(r=>setTimeout(r,0));}}
async function load({hash="#problems/"+key,remember=false,lost=false,completed=false,consent=true,lang="en",mutate=()=>{},missing=false,contextGate=null,statusGate=null,startError=null,startGate=null,storage=null,server=null,discover=false,retained={}}={}){
 const values=structuredClone(original),calls=[],polls=[],state=server||{row:null};mutate(values);
 values[`problems/${key}/investigation-context`].consent.enabled=consent;
 const dom=new JSDOM(html,{url:"http://vision/"+hash,runScripts:"outside-only"}),w=dom.window;
 if(storage)Object.defineProperty(w,"localStorage",{value:storage});
 Object.defineProperty(w.navigator,"language",{value:lang});Object.defineProperty(w.crypto,"randomUUID",{value:undefined});
 w.setInterval=()=>1;
 const nativeTimeout=w.setTimeout.bind(w);w.setTimeout=(fn,ms,...args)=>ms===750?(polls.push(fn),polls.length):nativeTimeout(fn,ms,...args);
 if(remember){w.localStorage.setItem("vision.operation."+key,JSON.stringify({operation_id:original["qa/completed"].operation_id}));state.row=structuredClone(values[completed?"qa/completed":"qa/running"]);}
 w.fetch=async(url,options={})=>{
  const path=url.replace(/^api\//,""),body=options.body&&JSON.parse(options.body);calls.push({path,method:options.method||"GET",body});
  if(contextGate && path===`problems/${key}/investigation-context` && !contextGate.used){contextGate.used=true;contextGate.entered=true;await new Promise(r=>contextGate.release=r);}
  if(discover&&path.endsWith("/investigation-context")&&values[path])return response({...values[path],operation:state.row?.problem_id===decodeURIComponent(path.split("/")[1])?state.row:null});
  if(path.startsWith("problems/")&&path.endsWith("/investigate")){
   const target=decodeURIComponent(path.split("/")[1]);
   assert.equal(JSON.parse(w.localStorage.getItem("vision.operation.pending."+target)).operation_id,body.operation_id,"Unconfirmed ID must be persisted before POST without replacing a confirmed pointer");
   if(startError){if(startGate){startGate.entered=true;await new Promise(r=>startGate.release=r);}return {ok:false,status:startError.status,json:async()=>({detail:startError.detail})};}
   const accepted={...structuredClone(values[completed||lost?"qa/completed":"qa/running"]),problem_id:target,revision:body.revision,operation_id:body.operation_id};state.row=accepted;
   if(startGate){startGate.entered=true;await new Promise(r=>startGate.release=r);}
   if(lost)throw Error("Synthetic lost 202");
   return response(accepted);
  }
  if(path==="home/investigation-consent"&&options.method==="POST"){
   values[path].enabled=body.enabled;values[`problems/${key}/investigation-context`].consent.enabled=body.enabled;return response(values[path]);
  }
  if(path.startsWith("home/investigations/")){
   if(path.endsWith("/audit"))return response(values["qa/audit"]);
   if(path.endsWith("/revoke")){state.row={...structuredClone(values["qa/revoked"]),operation_id:state.row.operation_id};return response(state.row);}
   if(statusGate&&path==="home/investigations/"+statusGate.id&&!statusGate.used){statusGate.used=true;statusGate.entered=true;await new Promise(r=>statusGate.release=r);}
   if(!missing&&retained[path.split("/")[2]])return response(retained[path.split("/")[2]]);
   if(missing||!state.row||path!=="home/investigations/"+state.row.operation_id)return {ok:false,status:404,json:async()=>({detail:"Investigation is not retained"})};
   return response(state.row);
  }
  if(path.startsWith("intelligence/analyses/"))return response(values["qa/analysis"]);
  if(path.startsWith("intelligence/requests/"))return response(values["qa/request"]);
  if(path.startsWith("intelligence/conversations/"))return response(values["qa/conversation"]);
  if(path==="intelligence/preview")return response(values["qa/request"]);
  if(values[path])return response(values[path]);
  throw Error("Unexpected one-click API: "+path);
 };
 w.eval(scripts+"\nwindow.__renderOneClick=render;");await until(()=>w.document.querySelector("#content > *"));
 return {w,doc:w.document,calls,values,state,polls};
}
const click=(s,selector)=>s.doc.querySelector(selector).click();

test("Separate authorization defaults off and page views perform no POST/research/provider work",async()=>{
 const s=await load({consent:false});try{
  assert.equal(s.doc.querySelector("#home-investigate-start"),null);
  assert.match(s.doc.querySelector(".home-investigation").textContent,/separate compact authorization/);
  assert.equal(s.calls.filter(c=>c.method!=="GET").length,0);
  assert.ok(s.doc.querySelector('#home-feedback'));
  assert.ok(s.doc.querySelector('.home-next-check').compareDocumentPosition(s.doc.querySelector('.home-investigation')) & s.w.Node.DOCUMENT_POSITION_FOLLOWING,"Local manual check precedes optional AI authorization");
 }finally{s.w.close();}
});

test("A new explicit click persists secure slot ID before one POST and reload only reads status",async()=>{
 const s=await load();try{
  click(s,"#home-investigate-start");await until(()=>s.doc.querySelector("#home-operation"));
  const post=s.calls.find(c=>c.path.endsWith("/investigate"));assert.match(post.body.operation_id,/^op1_\d+_[a-f0-9]{32}$/);
  assert.equal(post.body.revision,original[`problems/${key}/investigation-context`].revision);
  assert.equal(post.body.language,"en");assert.match(s.doc.querySelector("#home-operation").textContent,/AI investigation running/);
  await s.w.__renderOneClick();assert.equal(s.calls.filter(c=>c.path.endsWith("/investigate")).length,1);
  assert.ok(s.doc.querySelector("#home-operation-revoke"));
 }finally{s.w.close();}
 const reloaded=await load({remember:true});try{assert.ok(reloaded.doc.querySelector("#home-operation"));assert.equal(reloaded.calls.filter(c=>c.method==="POST").length,0);}finally{reloaded.w.close();}
});

test("Lost 202 followed by completed status shows received short result with exact audit link, never reposts",async()=>{
 const s=await load({lost:true});try{
  click(s,"#home-investigate-start");await until(()=>s.doc.querySelector("#home-human-result .finding-card"));
  assert.equal(s.calls.filter(c=>c.path.endsWith("/investigate")).length,1);
  assert.match(s.doc.querySelector("#home-operation").textContent,/Investigation received/);
  assert.ok([...s.doc.querySelectorAll("#home-operation a")].some(a=>a.hash.includes("?request="+original["qa/completed"].final_request_id)));
  assert.match(s.doc.querySelector(".finding-card h3").textContent,/Controleer voeding/);
  assert.equal(s.doc.querySelectorAll("#home-human-result .finding-card").length,1);
  assert.equal(s.doc.querySelectorAll("#home-human-result .finding-card ol li").length,2);
  click(s,"#home-operation-audit");await until(()=>s.doc.querySelector("#home-operation-audit-view details[open]"));
  assert.match(s.doc.querySelector("#home-operation-audit-view").textContent,/policy-authorized|query_plan|plan/);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,1);
 }finally{s.w.close();}
});

test("Explicit revoke retains the received result and audit without reopening automatic work",async()=>{
 const s=await load({remember:true});try{
  click(s,"#home-operation-revoke");await until(()=>s.doc.querySelector('#home-operation[data-status="revoked"] .finding-card'));
  assert.match(s.doc.querySelector("#home-operation").textContent,/Withdrawn/);
  assert.ok(s.doc.querySelector("#home-human-result"));
  assert.equal(s.calls.filter(c=>c.path.endsWith("/revoke")).length,1);
  assert.equal(s.calls.filter(c=>c.path.endsWith("/investigate")).length,0);
 }finally{s.w.close();}
});

test("Late revoked result and open audit survive progress polling without a second POST",async()=>{
 const s=await load({remember:true});try{
  click(s,"#home-operation-audit");await until(()=>s.doc.querySelector("#home-operation-audit-view details[open]"));
  const audit=s.doc.querySelector("#home-operation-audit-view");
  s.state.row={...s.values["qa/revoked"]};await s.polls.shift()();
  await until(()=>s.doc.querySelector("#home-human-result .finding-card"));
  assert.equal(s.doc.querySelector("#home-operation-audit-view"),audit);assert.ok(audit.querySelector("details[open]"));
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
 }finally{s.w.close();}
});

test("Missing old operation is explicit and neither reload nor polling replaces it with a new start",async()=>{
 const s=await load({remember:true,missing:true});try{
  assert.match(s.doc.querySelector(".home-investigation").textContent,/No request was restarted/);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);await s.w.__renderOneClick();
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
 }finally{s.w.close();}
});

test("Settings saves only explicit versioned consent, leaving provider options and old prose untouched",async()=>{
 const s=await load({hash:"#settings",consent:false});try{
  const form=s.doc.querySelector("#home-ai-consent");assert.equal(form.elements.enabled.checked,false);
  form.elements.enabled.checked=true;form.dispatchEvent(new s.w.Event("submit",{bubbles:true,cancelable:true}));
  await until(()=>s.calls.some(c=>c.path==="home/investigation-consent"&&c.method==="POST"));
  assert.deepEqual(s.calls.find(c=>c.method==="POST").body,{version:"vision-oneclick-compact-1",enabled:true});
  assert.equal(s.calls.filter(c=>c.method==="POST").length,1);
  await until(()=>s.doc.querySelector("#notice").textContent.includes("Authorization saved"));
 }finally{s.w.close();}
});

test("Local result cards escape provider text and keep full evidence/unknown prose behind disclosure",async()=>{
 const s=await load({remember:true,completed:true,lang:"nl-NL",mutate:v=>{
  const result=JSON.parse(v["qa/analysis"].result);result.diagnoses[0].title='<img src=x onerror="bad()">';
  v["qa/analysis"].result=JSON.stringify(result);
 }});try{
  await until(()=>s.doc.querySelector("#home-human-result .finding-card"));
  assert.equal(s.doc.querySelector("#home-human-result img"),null);
  assert.match(s.doc.querySelector(".finding-card h3").textContent,/<img/);
  assert.match(s.doc.querySelector(".finding-card").textContent,/AI-voorstel.*geen bewezen oorzaak/);
  assert.ok(s.doc.querySelector(".finding-card details"));
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
 }finally{s.w.close();}
});

test("Maximum-length v4 plans stay collapsed while the first manual check and all original details remain reachable",async()=>{
 const s=await load({remember:true,completed:true,mutate:v=>{
  const result=JSON.parse(v["qa/analysis"].result),base=result.diagnoses[0];
  base.title="T".repeat(120);base.core_explanation="C".repeat(400);base.next_check="N".repeat(240);
  base.validation="V".repeat(1000);base.finding="F".repeat(1500);base.uncertainty="U".repeat(1000);
  base.manual_plan={prerequisites:Array(4).fill("P".repeat(500)),steps:Array.from({length:4},()=>({instruction:"S".repeat(1000),source_refs:["source-ref"]}))};
  result.diagnoses=Array.from({length:4},()=>structuredClone(base));v["qa/analysis"].result=JSON.stringify(result);
 }});try{
  await until(()=>s.doc.querySelector("#home-human-result .finding-card"));
  const output=s.doc.querySelector("#home-human-result"),cards=output.querySelector(".finding-grid").children;
  assert.equal(cards.length,3);
  const card=cards[0],plan=card.querySelector(".human-manual-plan"),validation=card.querySelector(".human-validation");
  assert.equal(plan.open,false);assert.equal(validation.open,false);assert.equal(plan.querySelectorAll("ol li").length,4);
  assert.equal(card.querySelector("h4 + p").textContent,"N".repeat(240));
  plan.open=true;validation.open=true;
  assert.equal(plan.querySelector("ol li").firstChild.textContent.trim(),"S".repeat(1000));
  assert.equal(validation.querySelector("p").textContent,"V".repeat(1000));
  assert.ok([...output.querySelectorAll("details")].some(d=>d.querySelector("summary")?.textContent.includes("More retained proposals")&&!d.open));
 }finally{s.w.close();}
});

test("Completed one-click exact-request audit stays open with native bodies, digest and no replay button",async()=>{
 const s=await load({hash:"#intelligence/?request="+original["qa/completed"].final_request_id});try{
  await until(()=>s.doc.querySelector("#ai-preview #send-ai"));
  assert.equal(s.w.location.hash,"#intelligence/?request="+original["qa/completed"].final_request_id);
  assert.match(s.doc.querySelector("#ai-preview").textContent,/Policy-authorized compact investigation/);
  assert.ok(s.doc.querySelector("#ai-preview").textContent.includes(original["qa/request"].digest));
  assert.ok([...s.doc.querySelectorAll("#ai-preview pre")].some(p=>p.textContent===original["qa/request"].preview.requests.anthropic.body_utf8));
  assert.equal(s.doc.querySelector("#send-ai").disabled,true);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
 }finally{s.w.close();}
});

test("Delayed old dossier context cannot replace the actual visible problem's start binding",async()=>{
 const gate={},other=original["problems?mode=attention&page=1"].items.find(p=>p.problem_id!==key).problem_id;
 const s=await load({hash:"#today",contextGate:gate});try{
  s.w.location.hash="#problems/"+key;await until(()=>gate.entered);
  s.w.location.hash="#problems/"+other;await until(()=>s.doc.querySelector('.home-investigation')?.dataset.problem===other);
  gate.release();await new Promise(r=>setTimeout(r,0));
  assert.equal(s.doc.querySelector('.home-investigation').dataset.problem,other);
  click(s,"#home-investigate-start");await until(()=>s.calls.some(c=>c.path.endsWith("/investigate")));
  const request=s.calls.find(c=>c.path.endsWith("/investigate"));
  assert.equal(request.path,`problems/${other}/investigate`);
  assert.equal(request.body.revision,original[`problems/${other}/investigation-context`].revision);
  await until(()=>s.doc.querySelector("#home-operation")?.dataset.operation===request.body.operation_id);
 }finally{s.w.close();}
});

test("Delayed context A while remembered terminal B status awaits never starts A from visible B",async()=>{
 const gate={},saved=original["qa/other-completed"],statusGate={id:saved.operation_id},other=saved.problem_id;
 const s=await load({hash:"#today",contextGate:gate,statusGate});try{
  s.w.location.hash="#problems/"+key;await until(()=>gate.entered);
  s.state.row=structuredClone(saved);s.w.localStorage.setItem("vision.operation."+other,JSON.stringify({operation_id:saved.operation_id}));
  s.w.location.hash="#problems/"+other;await until(()=>statusGate.entered);
  gate.release();await new Promise(r=>setTimeout(r,0));statusGate.release();
  await until(()=>s.doc.querySelector('.home-investigation')?.dataset.problem===other&&s.doc.querySelector("#home-investigate-start"));
  click(s,"#home-investigate-start");await until(()=>s.calls.some(c=>c.path.endsWith("/investigate")));
  const request=s.calls.find(c=>c.path.endsWith("/investigate"));assert.equal(request.path,`problems/${other}/investigate`);
  assert.equal(request.body.revision,original[`problems/${other}/investigation-context`].revision);
  await until(()=>s.doc.querySelector("#home-operation")?.dataset.operation===request.body.operation_id);
 }finally{s.w.close();}
});

test("Manual exact-group preview retains group scope without representative device or selected run",async()=>{
 const s=await load({hash:"#intelligence/?task=availability&target_type=group&target=retained-group"});try{
  const form=s.doc.querySelector("#ai-form");assert.equal(form.elements.target_type.value,"group");
  assert.equal(form.elements.run_id.disabled,true);assert.equal(form.elements.compare.disabled,true);
  form.dispatchEvent(new s.w.Event("submit",{bubbles:true,cancelable:true}));
  await until(()=>s.doc.querySelector("#ai-preview #send-ai"));
  const request=s.calls.find(c=>c.path==="intelligence/preview");assert.equal(request.body.target_type,"group");
  assert.equal(request.body.target,"retained-group");assert.equal(request.body.run_id,null);
  assert.equal(s.calls.filter(c=>c.path.endsWith("/investigate")).length,0);
 }finally{s.w.close();}
});

test("Explicit manual v4 follow-up preserves original contract and language without automatic research/send",async()=>{
 const s=await load({hash:"#intelligence/?conversation="+original["qa/request"].conversation_id});try{
  const form=s.doc.querySelector("#ai-form");assert.equal(form.dataset.contract,"human-v4");
  assert.equal(form.dataset.language,"en");
  form.dispatchEvent(new s.w.Event("submit",{bubbles:true,cancelable:true}));
  await until(()=>s.doc.querySelector("#ai-preview #send-ai"));
  const request=s.calls.find(c=>c.path==="intelligence/preview");
  assert.equal(request.body.output_contract,"human-v4");assert.equal(request.body.language,"en");
  assert.equal(request.body.conversation_id,original["qa/request"].conversation_id);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,1);
 }finally{s.w.close();}
});

test("Conversation-only group follow-up keeps its exact group and v4 contract without a query target hint",async()=>{
 const s=await load({hash:"#intelligence/?conversation="+original["qa/request"].conversation_id,mutate:v=>{
  for(const round of v["qa/conversation"].rounds){round.target_type="group";round.target="retained-group";round.kind="availability";}
 }});try{
  const form=s.doc.querySelector("#ai-form");assert.equal(form.elements.target_type.value,"group");
  assert.equal(form.elements.target.value,"retained-group");assert.equal(form.elements.run_id.disabled,true);
  form.dispatchEvent(new s.w.Event("submit",{bubbles:true,cancelable:true}));
  await until(()=>s.doc.querySelector("#ai-preview #send-ai"));
  const request=s.calls.find(c=>c.path==="intelligence/preview");
  assert.equal(request.body.target_type,"group");assert.equal(request.body.target,"retained-group");
  assert.equal(request.body.output_contract,"human-v4");assert.equal(request.body.language,"en");
  assert.equal(request.body.run_id,null);assert.equal(request.body.compare,null);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,1);
 }finally{s.w.close();}
});

const sharedStorage=()=>{const rows=new Map();return {getItem:k=>rows.get(k)||null,setItem:(k,v)=>rows.set(k,String(v)),removeItem:k=>rows.delete(k)};};
for(const [status,detail] of [[400,"Consent changed"],[410,"Operation start window expired"],[409,"Selected revision changed"],[409,"Another investigation is busy"]]){
 test(`Definitive ${status} ${detail} leaves no false admitted pointer or automatic retry`,async()=>{
  const s=await load({startError:{status,detail}});try{
   click(s,"#home-investigate-start");await until(()=>s.doc.querySelector("#notice").textContent.includes("Start rejected")&&!s.doc.querySelector("#home-investigate-start").disabled);
   assert.equal(s.w.localStorage.getItem("vision.operation.pending."+key),null);
   assert.equal(s.w.localStorage.getItem("vision.operation."+key),null);
   assert.equal(s.w.location.hash,"#problems/"+key);assert.equal(s.doc.querySelector("#home-operation"),null);
   await s.w.__renderOneClick();assert.equal(s.calls.filter(c=>c.path.endsWith("/investigate")).length,1);
   click(s,"#home-investigate-start");await until(()=>s.calls.filter(c=>c.path.endsWith("/investigate")).length===2);
   const posts=s.calls.filter(c=>c.path.endsWith("/investigate"));assert.notEqual(posts[0].body.operation_id,posts[1].body.operation_id);
   await until(()=>!s.doc.querySelector("#home-investigate-start").disabled);
  }finally{s.w.close();}
 });
}

for(const rejection of [400,409,410])test(`Two same-problem tabs preserve the confirmed running pointer and revoke after stale rejection ${rejection}`,async()=>{
 const storage=sharedStorage(),server={row:null};
 const second=await load({storage,server,startError:{status:rejection,detail:"Investigation rejected"}}),first=await load({storage,server});
 try{
  click(first,"#home-investigate-start");await until(()=>first.doc.querySelector("#home-operation-revoke"));
  const confirmed=storage.getItem("vision.operation."+key),id=JSON.parse(confirmed).operation_id;
  click(second,"#home-investigate-start");await until(()=>second.doc.querySelector("#home-operation-revoke"));
  assert.equal(storage.getItem("vision.operation."+key),confirmed);
  assert.equal(storage.getItem("vision.operation.pending."+key),null);
  assert.equal(second.doc.querySelector("#home-operation").dataset.operation,id);
  assert.equal(new URLSearchParams(second.w.location.hash.split("?")[1]).get("operation"),id);
  assert.equal(second.calls.filter(c=>c.path.endsWith("/investigate")).length,1);
  click(second,"#home-operation-revoke");await until(()=>second.doc.querySelector('#home-operation[data-status="revoked"]'));
  assert.equal(second.calls.filter(c=>c.path.endsWith("/revoke")).length,1);
 }finally{first.w.close();second.w.close();}
});

test("A lost response with unknown status preserves only pending intent and reload performs no replacement POST",async()=>{
 const s=await load({lost:true,missing:true});try{
  click(s,"#home-investigate-start");await until(()=>s.doc.querySelector(".home-investigation").textContent.includes("Start is not confirmed"));
  const post=s.calls.find(c=>c.path.endsWith("/investigate"));
  assert.equal(JSON.parse(s.w.localStorage.getItem("vision.operation.pending."+key)).operation_id,post.body.operation_id);
  assert.equal(s.w.localStorage.getItem("vision.operation."+key),null);
  await s.w.__renderOneClick();assert.equal(s.calls.filter(c=>c.method==="POST").length,1);
  assert.match(s.doc.querySelector(".home-investigation").textContent,/Only status was checked/);
 }finally{s.w.close();}
});

test("A late accepted A response neither changes current B route nor overwrites a newer other-tab confirmation",async()=>{
 const storage=sharedStorage(),gate={},other=original["qa/other-completed"].problem_id;
 const s=await load({storage,startGate:gate});try{
  click(s,"#home-investigate-start");await until(()=>gate.entered);
  const newer={operation_id:original["qa/completed"].operation_id,revision:"newer-confirmed"};storage.setItem("vision.operation."+key,JSON.stringify(newer));
  s.w.location.hash="#problems/"+other;await until(()=>s.doc.querySelector(".home-investigation")?.dataset.problem===other);
  gate.release();await until(()=>s.doc.querySelector(".home-investigation")?.dataset.problem===other&&storage.getItem("vision.operation.pending."+key)===null);
  assert.equal(s.w.location.hash,"#problems/"+other);assert.deepEqual(JSON.parse(storage.getItem("vision.operation."+key)),newer);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,1);
 }finally{s.w.close();}
});

for(const result of [null,{diagnoses:"malformed"},{diagnoses:null}]){
 test(`Missing or non-array v4 diagnoses degrade locally without hiding dossier (${JSON.stringify(result)})`,async()=>{
  const s=await load({remember:true,completed:true,mutate:v=>{v["qa/analysis"].result=JSON.stringify(result);}});try{
   await until(()=>s.doc.querySelector("#home-human-result .human-findings"));
   assert.equal(s.doc.querySelectorAll("#home-human-result .finding-card").length,0);
   assert.match(s.doc.querySelector("#home-human-result").textContent,/No supported finding/);
   assert.ok(s.doc.querySelector("#home-feedback"));
  }finally{s.w.close();}
 });
}

test("Delayed rejection cannot remove another tab's pending/confirmed intent or change the current route",async()=>{
 const storage=sharedStorage(),gate={},other=original["qa/other-completed"].problem_id;
 const s=await load({storage,startGate:gate,startError:{status:409,detail:"Busy"}});try{
  click(s,"#home-investigate-start");await until(()=>gate.entered);
  const newer={operation_id:original["qa/completed"].operation_id};storage.setItem("vision.operation."+key,JSON.stringify(newer));
  const pending={operation_id:"different-other-tab-pending"};storage.setItem("vision.operation.pending."+key,JSON.stringify(pending));
  s.w.location.hash="#problems/"+other;await until(()=>s.doc.querySelector(".home-investigation")?.dataset.problem===other);
  const section=s.doc.querySelector(".home-investigation");gate.release();await new Promise(r=>setTimeout(r,10));
  assert.equal(s.w.location.hash,"#problems/"+other);assert.equal(s.doc.querySelector(".home-investigation"),section);
  assert.deepEqual(JSON.parse(storage.getItem("vision.operation."+key)),newer);
  assert.deepEqual(JSON.parse(storage.getItem("vision.operation.pending."+key)),pending);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,1);
 }finally{s.w.close();}
});

test("Accepted delayed first tab confirms after second fresh tab replaces and rejects pending intent",async()=>{
 const storage=sharedStorage(),server={row:null},gate={};
 const first=await load({storage,server,startGate:gate}),second=await load({storage,server,startError:{status:409,detail:"Busy"}});
 let reopened;try{
  click(first,"#home-investigate-start");await until(()=>gate.entered);
  const accepted=first.calls.find(c=>c.path.endsWith("/investigate")).body;
  assert.equal(storage.getItem("vision.operation."+key),null);
  click(second,"#home-investigate-start");await until(()=>second.doc.querySelector("#notice").textContent.includes("Start rejected")&&!second.doc.querySelector("#home-investigate-start").disabled);
  assert.equal(storage.getItem("vision.operation.pending."+key),null);
  assert.equal(storage.getItem("vision.operation."+key),null);
  gate.release();await until(()=>JSON.parse(storage.getItem("vision.operation."+key)||"null")?.operation_id===accepted.operation_id);
  await until(()=>first.doc.querySelector("#home-operation-revoke"));
  reopened=await load({storage,server});assert.equal(reopened.w.location.hash,"#problems/"+key);
  assert.equal(reopened.doc.querySelector("#home-operation").dataset.operation,accepted.operation_id);
  assert.ok(reopened.doc.querySelector("#home-operation-revoke"));
  assert.equal(reopened.calls.filter(c=>c.method==="POST").length,0);
 }finally{first.w.close();second.w.close();reopened?.w.close();}
});

test("Lost first response after rejected second pending confirms via status and remains reachable without URL parameters",async()=>{
 const storage=sharedStorage(),server={row:null},gate={};let reopened;
 const first=await load({storage,server,startGate:gate,lost:true,mutate:v=>{v["qa/completed"]=structuredClone(v["qa/running"]);}});
 const second=await load({storage,server,startError:{status:409,detail:"Busy"}});
 try{
  click(first,"#home-investigate-start");await until(()=>gate.entered);
  const id=first.calls.find(c=>c.path.endsWith("/investigate")).body.operation_id;
  click(second,"#home-investigate-start");
  await until(()=>second.doc.querySelector("#notice").textContent.includes("Start rejected")&&!second.doc.querySelector("#home-investigate-start").disabled);
  gate.release();await until(()=>first.doc.querySelector("#home-operation-revoke"));
  assert.equal(JSON.parse(storage.getItem("vision.operation."+key)||"null")?.operation_id,id);
  reopened=await load({storage,server});
  assert.equal(reopened.doc.querySelector("#home-operation").dataset.operation,id);
  assert.ok(reopened.doc.querySelector("#home-operation-revoke"));
  assert.equal(reopened.calls.filter(c=>c.method==="POST").length,0);
 }finally{first.w.close();second.w.close();reopened?.w.close();}
});

test("An exact old-URL status read with no pending intent never replaces an existing other-tab confirmation",async()=>{
 const storage=sharedStorage(),row=original["qa/running"],newer={operation_id:"newer-confirmed-operation",revision:"newer"};
 storage.setItem("vision.operation."+key,JSON.stringify(newer));
 const s=await load({storage,server:{row},hash:"#problems/"+key+"?operation="+row.operation_id});try{
  await until(()=>s.doc.querySelector("#home-operation-revoke"));
  assert.equal(s.doc.querySelector("#home-operation").dataset.operation,row.operation_id);
  assert.deepEqual(JSON.parse(storage.getItem("vision.operation."+key)),newer);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
 }finally{s.w.close();}
});

test("A history restore failure after dispatched 409 reports rejection/status-only and keeps valid running revoke",async()=>{
 const storage=sharedStorage(),server={row:null};
 const second=await load({storage,server,startError:{status:409,detail:"Busy"}}),first=await load({storage,server});try{
  click(first,"#home-investigate-start");await until(()=>first.doc.querySelector("#home-operation-revoke"));
  const confirmed=storage.getItem("vision.operation."+key),replace=second.w.history.replaceState.bind(second.w.history);let count=0;
  second.w.history.replaceState=(...args)=>{if(++count===2)throw Error("Synthetic navigation throttle");return replace(...args);};
  click(second,"#home-investigate-start");await until(()=>second.doc.querySelector("#home-operation-revoke"));
  assert.match(second.doc.querySelector("#notice").textContent,/Start rejected; no new operation admitted.*Status lookup only/);
  assert.doesNotMatch(second.doc.querySelector("#notice").textContent,/no work started|nothing.*sent/i);
  assert.equal(storage.getItem("vision.operation."+key),confirmed);assert.equal(storage.getItem("vision.operation.pending."+key),null);
  assert.equal(second.calls.filter(c=>c.path.endsWith("/investigate")).length,1);
  assert.equal(second.doc.querySelector("#home-operation").dataset.operation,JSON.parse(confirmed).operation_id);
 }finally{first.w.close();second.w.close();}
});

test("A pre-dispatch history failure reports no work and makes no start POST",async()=>{
 const s=await load();try{
  s.w.history.replaceState=()=>{throw Error("Synthetic history unavailable before POST");};
  click(s,"#home-investigate-start");await until(()=>s.doc.querySelector("#notice").textContent.includes("no work started"));
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
  assert.equal(s.w.localStorage.getItem("vision.operation."+key),null);
 }finally{s.w.close();}
});

for(const scene of ["running","completed"])test(`Fresh browser with no local pointer discovers retained ${scene} operation from real context DTO`,async()=>{
 const context=original[`qa/${scene}-context`],row=original[`qa/${scene}`];
 const s=await load({mutate:v=>{v[`problems/${key}/investigation-context`]=structuredClone(context);},server:{row}});try{
  await until(()=>s.doc.querySelector("#home-operation"));
  assert.equal(s.doc.querySelector("#home-operation").dataset.operation,row.operation_id);
  assert.equal(JSON.parse(s.w.localStorage.getItem("vision.operation."+key)).operation_id,row.operation_id);
  if(scene==="running")assert.ok(s.doc.querySelector("#home-operation-revoke"));
  else await until(()=>s.doc.querySelector("#home-human-result .finding-card"));
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
 }finally{s.w.close();}
});

test("Server discovery recovers newer admitted work over older confirmed A after lost B response and rejected C",async()=>{
 const storage=sharedStorage(),server={row:structuredClone(original["qa/completed"])},gate={};let reopened;
 const old=server.row;storage.setItem("vision.operation."+key,JSON.stringify({operation_id:old.operation_id}));
 const first=await load({storage,server,startGate:gate,lost:true,discover:true,mutate:v=>{v["qa/completed"]=structuredClone(v["qa/running"]);}});
 const second=await load({storage,server,startError:{status:409,detail:"Busy"},discover:true});try{
  click(first,"#home-investigate-start");await until(()=>gate.entered);
  const id=first.calls.find(c=>c.path.endsWith("/investigate")).body.operation_id;
  click(second,"#home-investigate-start");await until(()=>second.doc.querySelector("#home-operation-revoke"));
  gate.release();await until(()=>first.doc.querySelector("#home-operation-revoke"));
  reopened=await load({storage,server,discover:true});
  assert.equal(reopened.doc.querySelector("#home-operation").dataset.operation,id);
  assert.ok(reopened.doc.querySelector("#home-operation-revoke"));
  assert.equal(JSON.parse(storage.getItem("vision.operation."+key)).operation_id,id);
  assert.equal(reopened.calls.filter(c=>c.method==="POST").length,0);
 }finally{first.w.close();second.w.close();reopened?.w.close();}
});

test("Explicit older operation remains inspectable while current active work has a visible route to revoke",async()=>{
 const old=original["qa/completed"],current={...original["qa/running"],operation_id:"newer-current-operation"},storage=sharedStorage();
 const s=await load({storage,server:{row:current},discover:true,retained:{[old.operation_id]:old},hash:"#problems/"+key+"?operation="+old.operation_id});try{
  await until(()=>s.doc.querySelector("#home-human-result .finding-card"));
  assert.equal(s.doc.querySelector("#home-operation").dataset.operation,old.operation_id);
  const link=s.doc.querySelector(".current-investigation");assert.ok(link);assert.match(link.textContent,/current investigation.*withdraw/);
  assert.equal(new URLSearchParams(link.hash.split("?")[1]).get("operation"),current.operation_id);
  assert.equal(JSON.parse(storage.getItem("vision.operation."+key)).operation_id,current.operation_id);
  link.click();await until(()=>s.doc.querySelector("#home-operation")?.dataset.operation===current.operation_id);
  assert.ok(s.doc.querySelector("#home-operation-revoke"));assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
 }finally{s.w.close();}
});
