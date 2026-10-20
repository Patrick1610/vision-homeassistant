"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {readFileSync, existsSync} = require("node:fs");
const {resolve} = require("node:path");
const {spawnSync} = require("node:child_process");
const {JSDOM} = require("jsdom");
const root=resolve(__dirname,"../..");
const script=readFileSync(resolve(root,"vision/static/app.js"),"utf8");
const html=readFileSync(resolve(root,"vision/static/index.html"),"utf8");

test("real POST and retained GET show the same exact device/entity/system scope in shipped DOM",async()=>{
 const localPython=resolve(root,".venv/bin/python");
 const generated=spawnSync(existsSync(localPython)?localPython:"python3",[resolve(__dirname,"retained_request_fixture.py")],{cwd:root,encoding:"utf8",maxBuffer:4*1024*1024,timeout:30000});
 if(generated.error)assert.fail(`ASGI fixture setup/startup failed (${generated.error.code || generated.error.message}). Install locked Python test dependencies before npm test; fixture deadline is 30 seconds.`);
 if(generated.status!==0){
  const setup=/ModuleNotFoundError|ImportError|No module named/.test(generated.stderr);
  assert.fail(`${setup ? "ASGI fixture setup is incomplete: install locked Python dependencies and use the checked-out source before npm test." : "Actual ASGI fixture execution failed before DOM replay."}\n${generated.stderr}`);
 }
 const fixtures=JSON.parse(generated.stdout);
 assert.equal(fixtures[0].retained.local_selection.entity,null);
 assert.equal(fixtures[0].retained.local_selection.device,fixtures[0].expected);
 for(const fixture of fixtures) for(const shape of ["post","retained"]){
  const value=fixture[shape];
  const dom=new JSDOM(html,{url:`http://vision/#intelligence/?request=${value.request_id}`,runScripts:"outside-only"});
  const writes=[];
  dom.window.fetch=async(url,options={})=>{
   if(options.method && options.method!=="GET")writes.push(url);
   let data;
   if(url==="api/health")data={connected:true};
   else if(url==="api/intelligence")data={enabled:true,running:false,privacy:"compact",tasks:{availability:{title:"Availability"},audit:{title:"Audit"}},analyses:[],usage:[]};
   else if(url===`api/intelligence/requests/${value.request_id}`)data=value;
   else throw Error("Unexpected audit route "+url);
   return {ok:true,json:async()=>data};
  };
  try{
   dom.window.eval(script);
   const deadline=performance.now()+1500;
   while(!dom.window.document.querySelector("#revoke-ai")){
    assert.ok(performance.now()<deadline,"Whole-app request readiness");
    await new Promise(r=>setTimeout(r,0));
   }
   const panel=dom.window.document.querySelector("#ai-preview");
   const target=[...panel.querySelectorAll("p")].find(p=>p.textContent.startsWith("Local target "));
   assert.ok(target.textContent.startsWith(`Local target ${fixture.expected} · Run None · Compare None`),`${shape}: ${target.textContent}`);
   assert.ok(panel.textContent.includes(value.digest));
   assert.ok(Object.keys(value.preview.requests).length>0,"Fixture has an actual native body");
   for(const provider of Object.values(value.preview.requests))assert.ok(panel.textContent.includes(provider.body_utf8));
   assert.equal(writes.length,0,"Opening an audit performs no send/revoke/research");
  }finally{dom.window.close();}
 }
});
