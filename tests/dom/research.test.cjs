"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { JSDOM } = require("jsdom");
const root = resolve(__dirname, "../..");
const html = readFileSync(resolve(root, "vision/static/index.html"), "utf8");
const script = readFileSync(resolve(root, "vision/static/app.js"), "utf8");
const base = "a".repeat(32), prepared = "b".repeat(32), job = "c".repeat(32);
const response = (data, ok=true) => ({ok, json: async()=>data});
const source = {kind:"official_docs",url:"https://www.home-assistant.io/integrations/zha/",title:"Public <source>",content_sha256:"s".repeat(64),response_sha256:"h".repeat(64),retrieved_at:1000,applicability:"unknown",excerpts:[{excerpt_key:"p1",heading:"Manual check",text:"Inspect power; no cause proved.",ref:"Rnew:S1:P1"}]};
const research = {sources:[source],technical_context:{core_version:"2026.10.2"},gaps:[{adapter:"reddit",reason:"authentication_required"},{adapter:"public_transport",reason:"upstream_backoff",host:"api.github.com",until:2000000000}],query_plan:{integration:"zha"},coverage:{thread_complete:false}};
function request(id=base) {return {request_id:id,digest:(id===base?"d":"e").repeat(64),status:"preview",in_flight:false,local_selection:{target:"private-device",target_type:"device"},local_mapping:{},local_aliases:{},preview:{round:1,task:"availability",target_type:"device",profile:"compact",bundle:{captured_at:1000},readiness:{supported:true},policy:{providers:{anthropic:{model:"synthetic-a"},openai:{model:"synthetic-b"}}},requests:{anthropic:{url:"https://api.anthropic.com/v1/messages",body_utf8:id===base?"LOCAL-EXACT-A":"SOURCED-EXACT-A"},openai:{url:"https://api.openai.com/v1/responses",body_utf8:id===base?"LOCAL-EXACT-B":"SOURCED-EXACT-B"}},...(id===prepared?{research,schema_version:"vision-diagnosis-3"}:{})}};}
async function until(fn) { const deadline=performance.now()+1500; while(!fn()) {if(performance.now()>deadline) assert.fail("Shipped app did not reach research DOM state"); await new Promise(r=>setTimeout(r,0));} }
async function load({resume=false,diagnostic=false,attachError=false,terminal="completed",index=false}={}) {
 const dom=new JSDOM(html,{url:index?"http://vision/#intelligence":`http://vision/#intelligence/?request=${base}${resume?`&research=${job}`:""}`,runScripts:"outside-only"});
 const calls=[];
 const analysis={id:42,provider:"synthetic",model:"synthetic",created:1000,can_continue:false,evidence:JSON.stringify({research,request_id:prepared}),result:JSON.stringify({summary:"Selected solution",diagnoses:[{finding:"Check availability manually",severity:"warning",uncertainty:"Cause unknown",unknowns:["Physical check missing"],evidence:["Rnew:E1"],counter_evidence:[],next_step:"Manual inspection",validation:"Compare later covered observations",source_refs:["Rnew:S1:P1"],manual_plan:{prerequisites:["Confirm compatible version"],steps:[{instruction:"Inspect power manually",source_refs:["Rnew:S1:P1"]},{instruction:"Compare healthy members",source_refs:["Rnew:S1:P1"]}]}}]})};
 dom.window.fetch=async(url,options={})=>{
  calls.push({url,options});
  if(url==="api/health")return response({connected:true});
  if(url==="api/intelligence" && options.method!=="POST") return response({enabled:true,running:false,privacy:diagnostic?"diagnostic":"compact",tasks:{availability:{title:"Availability"}},analyses:index?[{id:42,summary:"Selected solution"},{id:41,summary:"Older compact history"}]:[],usage:[]});
  if(url==="api/intelligence/analyses/42")return response(analysis);
  if(url===`api/intelligence/requests/${base}`) { const r=request(); if(diagnostic)r.preview.profile="diagnostic"; return response(r); }
  if(url===`api/intelligence/requests/${prepared}`) return response({...request(prepared),status:"completed",analysis_id:42});
  if(url==="api/intelligence/research/plan") return response({plan_id:"f".repeat(32),plan_digest:"1".repeat(64),plan:{problem_class:"availability",integration:"zha",requests:[{kind:"official_docs",url:source.url}]}});
  if(url==="api/intelligence/research" && options.method==="POST")return response({research_id:job,status:"running"});
  if(url===`api/intelligence/research/${job}/status`) return response({research_id:job,status:terminal,attempts:1,source_count:1});
  if(url===`api/intelligence/research/${job}`) return response({research_id:job,status:terminal,attempts:1,source_count:1,research_digest:"2".repeat(64),snapshot:research});
  if(url===`api/intelligence/research/${job}/preview`) return attachError?response({detail:"Fresh diagnostic consent required"},false):response(request(prepared));
  if(url.endsWith("/revoke"))return response({revoked:true});
  if(url==="api/intelligence" && options.method==="POST")return response({request_id:prepared});
  throw Error("Unmocked research DOM request "+url);
 };
 dom.window.eval(script);
 await until(()=>dom.window.document.querySelector(index?".finding-card":"#plan-research"));
 return {dom,doc:dom.window.document,calls};
}

test("public plan is inspected before fetching; new exact preview precedes paid send",async()=>{
 const app=await load(); try {
  app.doc.querySelector("#plan-research").click();
  await until(()=>app.doc.querySelector("#start-research"));
  assert.equal(app.calls.filter(c=>c.url==="api/intelligence/research").length,0);
  assert.match(app.doc.querySelector("#public-research").textContent,/Plan SHA-256/);
  assert.doesNotMatch(app.doc.querySelector("#public-research").textContent,/private-device/);
  app.doc.querySelector("#start-research").click();
  await until(()=>app.doc.querySelector("#attach-research"));
  assert.match(app.dom.window.location.hash,/research=/);
  assert.ok(app.doc.querySelector("#send-ai").disabled);
  assert.equal(app.calls.filter(c=>c.url==="api/intelligence"&&c.options.method==="POST").length,0);
  app.doc.querySelector("#attach-research").click();
  await until(()=>app.doc.querySelector("#ai-preview").textContent.includes("SOURCED-EXACT-B"));
  const preview=app.doc.querySelector("#ai-preview");
  assert.match(preview.textContent,/SOURCED-EXACT-A/);
  assert.match(preview.textContent,/Inspect power; no cause proved/);
  assert.match(preview.textContent,/s{64}/);
  assert.match(preview.textContent,/api\.github\.com until/);
  assert.equal(app.doc.querySelector("#send-ai").disabled,false);
  assert.deepEqual(JSON.parse(app.calls.find(c=>c.url.endsWith(`${job}/preview`)).options.body),{research_digest:"2".repeat(64),diagnostic_consent:false});
  app.doc.querySelector("#send-ai").click();
  await until(()=>app.doc.querySelector(".finding-card"));
  const sent=app.calls.find(c=>c.url==="api/intelligence"&&c.options.method==="POST");
  assert.deepEqual(JSON.parse(sent.options.body),{request_id:prepared,digest:"e".repeat(64)});
  assert.match(app.doc.querySelector(".manual-steps").textContent,/Inspect power manually/);
  assert.match(app.doc.querySelector(".validation-block").textContent,/Compare later covered/);
  const link=app.doc.querySelector(".manual-steps a");
  assert.equal(link.href,source.url); assert.match(link.rel,/noreferrer/);
  assert.equal(app.doc.querySelector("source"),null);
 } finally {app.dom.window.close();}
});

test("research resume retrieves light status, without another start or paid send",async()=>{
 const app=await load({resume:true}); try {
  await until(()=>app.doc.querySelector("#attach-research"));
  assert.equal(app.calls.filter(c=>c.url==="api/intelligence/research"&&c.options.method==="POST").length,0);
  assert.equal(app.calls.filter(c=>c.url==="api/intelligence"&&c.options.method==="POST").length,0);
  assert.equal(app.doc.querySelector("#send-ai").disabled,true);
 }finally{app.dom.window.close();}
});

test("source attachment requires fresh diagnostic consent and preserves failed preview",async()=>{
 const app=await load({resume:true,diagnostic:true,attachError:true});try{
  await until(()=>app.doc.querySelector("#attach-research"));
  app.doc.querySelector("#attach-research").click();
  await until(()=>app.doc.querySelector("#notice").textContent.includes("Fresh diagnostic"));
  assert.equal(JSON.parse(app.calls.find(c=>c.url.endsWith(`${job}/preview`)).options.body).diagnostic_consent,false);
  assert.ok(app.doc.querySelector("#send-ai").disabled);
  assert.equal(app.doc.querySelector("#attach-research").disabled,false);
 }finally{app.dom.window.close();}
});

test("failed or withdrawn research never silently attaches or sends",async()=>{
 for(const terminal of ["failed","revoked"]) {
  const app=await load({resume:true,terminal});try{
   await until(()=>app.doc.querySelector("#public-research").textContent.includes(`Public research: ${terminal}`));
   assert.equal(app.doc.querySelector("#attach-research"),null);
   assert.ok(app.doc.querySelector("#send-ai").disabled);
   assert.equal(app.calls.filter(c=>c.url.endsWith("/preview")).length,0);
  }finally{app.dom.window.close();}
 }
});

test("Intelligence centers only selected/latest solution and keeps older history compact",async()=>{
 const app=await load({index:true});try{
  assert.equal(app.doc.querySelectorAll(".finding-card").length,1);
  assert.equal(app.calls.filter(c=>c.url.startsWith("api/intelligence/analyses/")).length,1);
  const older=[...app.doc.querySelectorAll("a")].find(a=>a.href.includes("analysis=41"));
  assert.ok(older); assert.match(older.closest("article").textContent,/Older compact history/);
  assert.ok(app.doc.querySelector(".manual-steps"));
 }finally{app.dom.window.close();}
});

test("fresh diagnostic source consent is separate from editing/revoking the original preview",async()=>{
 const app=await load({resume:true,diagnostic:true});try{
  await until(()=>app.doc.querySelector("#research-consent"));
  const consent=app.doc.querySelector("#research-consent");
  consent.checked=true;
  consent.dispatchEvent(new app.dom.window.Event("input",{bubbles:true}));
  app.doc.querySelector("#attach-research").click();
  await until(()=>app.doc.querySelector("#ai-preview").textContent.includes("SOURCED-EXACT-A"));
  assert.equal(JSON.parse(app.calls.find(c=>c.url.endsWith(`${job}/preview`)).options.body).diagnostic_consent,true);
  assert.equal(app.calls.filter(c=>c.url.endsWith("/revoke")).length,0);
  assert.equal(app.calls.filter(c=>c.url==="api/intelligence"&&c.options.method==="POST").length,0);
 }finally{app.dom.window.close();}
});
