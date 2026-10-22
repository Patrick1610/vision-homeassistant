"use strict";
const {test}=require("node:test"),assert=require("node:assert/strict");
const {readFileSync,existsSync}=require("node:fs"),{resolve}=require("node:path"),{spawnSync}=require("node:child_process"),{JSDOM}=require("jsdom");
const root=resolve(__dirname,"../.."), python=existsSync(resolve(root,".venv/bin/python"))?resolve(root,".venv/bin/python"):"python";
const generated=spawnSync(python,[resolve(__dirname,"home_fixture.py")],{cwd:root,encoding:"utf8",timeout:30000});
assert.equal(generated.status,0,`Install requirements-test.txt before DOM tests. Source ASGI fixture failed: ${generated.stderr}`);
const original=JSON.parse(generated.stdout),html=readFileSync(resolve(root,"vision/static/index.html"),"utf8"),home=readFileSync(resolve(root,"vision/static/home.js"),"utf8"),app=readFileSync(resolve(root,"vision/static/app.js"),"utf8");
const response=data=>({ok:true,json:async()=>structuredClone(data)});
async function until(predicate){const deadline=performance.now()+2000;while(!predicate()){if(performance.now()>deadline)assert.fail("Shipped Home UI did not reach expected state");await new Promise(r=>setTimeout(r,0));}}
async function load({hash="#today",lang="en",mutate=()=>{},setup=()=>{},feedbackFailures=0,preferencesState={fail:false}}={}){
 const values=structuredClone(original), calls=[];mutate(values);
 const dom=new JSDOM(html,{url:"http://vision/"+hash,runScripts:"outside-only"});const w=dom.window;
 Object.defineProperty(w.navigator,"language",{value:lang});w.setInterval=()=>1;w.confirm=()=>true;setup(w);
 w.fetch=async(url,options={})=>{const path=url.replace(/^api\//,"");calls.push({path,method:options.method||"GET",body:options.body&&JSON.parse(options.body)});
   if(path==="home/preferences"&&options.method!=="POST"&&preferencesState.fail)return {ok:false,json:async()=>({detail:"Synthetic locale unavailable"})};
   if(options.method==="POST"){
    const body=JSON.parse(options.body);
    if(path==="home/preferences"){
     if(preferencesState.postFailures>0){preferencesState.postFailures--;return {ok:false,json:async()=>({detail:"Synthetic preferences save failed"})};}
     if(body.locale)values["home/preferences"].locale=values["today?window=24h"].preferences.locale=body.locale;
     return response(values["home/preferences"]);
    }
    if(path.endsWith("/feedback")){if(feedbackFailures-->0)throw Error("Synthetic transport failure");const detail=structuredClone(values[path.replace(/\/feedback$/,"")]);detail.feedback.push({...body,created:1000});return response(detail);}
   }
   if(values[path])return response(values[path]);
   throw Error("Unexpected daily-journey API call: "+path);
 };
 w.eval(home+"\n"+app+"\nwindow.__renderHome=render;");await until(()=>w.document.querySelector("#content > *"));
 return {dom,w,doc:w.document,calls,values};
}
const click=(w,selector)=>w.document.querySelector(selector).click();
const event=(w,node,type)=>node.dispatchEvent(new w.Event(type,{bubbles:true,cancelable:true}));

test("Five visible primary routes, friendly priorities, one primary CTA and preserved expert links",async()=>{
 const s=await load();try{
  assert.deepEqual([...s.doc.querySelectorAll("#nav a")].map(a=>a.textContent),["Today","Problems","Devices","History","Settings"]);
  assert.equal(s.doc.querySelectorAll(".home-primary").length,1);assert.equal(s.doc.querySelectorAll(".today-priority").length,2);
  assert.match(s.doc.querySelector(".today-priority h2").textContent,/Friendly lamp/);
  assert.ok(!s.doc.querySelector(".today-priority h2").textContent.includes("d0"));
  assert.match(s.doc.querySelector("#expert-links").textContent,/Automations.*Source cases.*Expert research/);
  assert.equal(s.calls.filter(c=>c.method!=="GET").length,0);
  click(s.w,".home-primary");await until(()=>s.doc.querySelector("#home-feedback"));
  assert.match(s.doc.querySelector("#content").textContent,/Your first manual check/);
  assert.match(s.doc.querySelector("#content").textContent,/How to check the result/);
 }finally{s.w.close();}
});

test("Dutch daily labels, connection, chart legend and accessible text follow browser locale",async()=>{
 const s=await load({lang:"nl-NL"});try{
  assert.equal(s.doc.documentElement.lang,"nl");
  assert.equal(s.doc.querySelector("#nav a").textContent,"Vandaag");
  assert.match(s.doc.querySelector("#connection").textContent,/Verbonden.*Alleen lezen/);
  assert.match(s.doc.querySelector(".chart-legend").textContent,/Aanhoudend.*Onbekende dekking/);
  assert.match(s.doc.querySelector("svg[role=img]").getAttribute("aria-label"),/waargenomen/);
 }finally{s.w.close();}
});

test("Intake cancel writes nothing; importance, known and usual are independent controls",async()=>{
 const s=await load({hash:"#intake"});try{
  const row=s.doc.querySelector(".home-device"),importance=row.querySelector("select"),known=row.querySelector('[data-field="known_issue"]'),usual=row.querySelector('[data-field="usual_behavior"]');
  importance.value="high";event(s.w,importance,"change");known.checked=true;event(s.w,known,"change");usual.checked=true;event(s.w,usual,"change");
  click(s.w,"#home-cancel");await until(()=>s.doc.querySelector(".home-primary"));
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
  s.w.location.hash="#intake";await until(()=>s.doc.querySelector("#home-intake"));
  assert.equal(s.doc.querySelector('[data-field="known_issue"]').checked,false);
 }finally{s.w.close();}
});

test("Save-for-later sends only edited devices and preserves distinct true/false values",async()=>{
 const s=await load({hash:"#intake"});try{
  const row=s.doc.querySelector(".home-device"),known=row.querySelector('[data-field="known_issue"]');known.checked=true;event(s.w,known,"change");
  const button=s.doc.querySelector('button[value="draft"]');button.click();await until(()=>s.calls.some(c=>c.method==="POST"));
  const request=s.calls.find(c=>c.method==="POST");assert.equal(request.path,"home/preferences");
  assert.equal(request.body.intake,"draft");assert.equal(request.body.devices.length,1);
  assert.equal(request.body.devices[0].known_issue,true);assert.equal(Object.hasOwn(request.body.devices[0],"usual_behavior"),false);
  await until(()=>s.w.location.hash==="#today"&&s.doc.querySelector(".home-primary"));
  assert.equal(Object.hasOwn(request.body,"locale"),false);assert.ok(!JSON.stringify(request.body).includes("acknowledge_worsening"));
 }finally{s.w.close();}
});

test("Subjective report retains offline observation; no provider/HA action is requested",async()=>{
 const id=original["problems?mode=attention&page=1"].items[0].problem_id;
 const s=await load({hash:"#problems/"+id});try{
  const form=s.doc.querySelector("#home-feedback"),select=form.querySelector("select");select.value="seems_recovered";
  form.querySelector("textarea").value="Manual observation";event(s.w,form,"submit");await until(()=>s.calls.some(c=>c.path.endsWith("/feedback")));
  const sent=s.calls.find(c=>c.path.endsWith("/feedback"));assert.equal(sent.body.kind,"seems_recovered");
  assert.equal(sent.body.episode,original["problems/"+id].problem.episode);
  await until(()=>s.doc.querySelector("#home-feedback")!==form);
  assert.match(s.doc.querySelector("#content").textContent,/Unavailable signals/);
  assert.ok(s.calls.every(c=>!c.path.startsWith("intelligence")&&!c.path.includes("services")));
 }finally{s.w.close();}
});

test("Coverage-limited Today does not become all healthy or show stale actionable cards",async()=>{
 const s=await load({mutate:v=>{v["today?window=24h"].status="limited";v["today?window=24h"].priorities=[];}});try{
  assert.match(s.doc.querySelector(".today-hero").textContent,/Not enough visibility/);
  assert.equal(s.doc.querySelectorAll(".today-priority").length,0);
 }finally{s.w.close();}
});

test("Background refresh preserves focused local drafts and open evidence disclosures",async()=>{
 const id=original["problems?mode=attention&page=1"].items[0].problem_id;
 const s=await load({hash:"#problems/"+id});try{
  const input=s.doc.querySelector("textarea");input.value="Keep my draft";input.focus();const before=s.doc.querySelector("#content").innerHTML;
  await s.w.__renderHome({background:true});assert.equal(s.doc.querySelector("#content").innerHTML,before);assert.equal(s.doc.activeElement,input);
 }finally{s.w.close();}
});

test("Healthy device opens its exact existing evidence route instead of an invented problem",async()=>{
 const s=await load({hash:"#devices"});try{
  const healthy=[...s.doc.querySelectorAll(".home-device")].find(row=>row.textContent.includes("Friendly lamp 2"));
  const anchor=healthy.querySelector("a");assert.equal(anchor.hash,"#devices/reliability?device=d2");
  anchor.click();await until(()=>s.doc.querySelector("#device-check-form"));
  assert.equal(s.doc.querySelector("#device-check-form").dataset.device,"d2");
 }finally{s.w.close();}
});

test("Declared local impact is concrete before technical details without a causal promise",async()=>{
 const id=original["problems?mode=attention&page=1"].items.find(p=>p.target==="d0").problem_id;
 const s=await load({hash:"#problems/"+id});try{
  const why=[...s.doc.querySelectorAll(".home-section")].find(n=>n.querySelector("h2")?.textContent==="Why it matters");
  assert.match(why.textContent,/Evening lighting/);assert.match(why.textContent,/not guaranteed/);
  assert.equal(why.querySelector("a").hash,"#automations/automation.evening");
 }finally{s.w.close();}
});

test("Plain HTTP feedback works without randomUUID and retries keep the same idempotency key",async()=>{
 const id=original["problems?mode=attention&page=1"].items[0].problem_id;
 const s=await load({hash:"#problems/"+id,feedbackFailures:1,setup:w=>Object.defineProperty(w.crypto,"randomUUID",{value:undefined})});try{
  const form=s.doc.querySelector("#home-feedback");event(s.w,form,"submit");
  await until(()=>s.doc.querySelector("#notice").textContent.includes("Synthetic transport failure"));
  assert.equal(form.querySelector("button").disabled,false);
  event(s.w,form,"submit");await until(()=>s.doc.querySelector("#home-feedback")!==form);
  const sent=s.calls.filter(c=>c.path.endsWith("/feedback"));assert.equal(sent.length,2);
  assert.match(sent[0].body.request_id,/^[a-f0-9]{32}$/);assert.equal(sent[0].body.request_id,sent[1].body.request_id);
 }finally{s.w.close();}
});

test("Explicit server locale wins on direct Problems, Devices, Intake, Settings and History links",async()=>{
 for(const [hash,heading] of [["#problems","Problems"],["#devices","Devices"],["#intake","Your preferences"],["#settings","Settings"],["#history","History"]]){
  const s=await load({hash,lang:"nl-NL",mutate:v=>v["home/preferences"].locale="en"});try{
   assert.equal(s.doc.documentElement.lang,"en");assert.equal(s.doc.querySelector("#title").textContent,heading);
   assert.equal(s.doc.querySelector("#nav a").textContent,"Today");assert.ok(s.calls.some(c=>c.path==="home/preferences"));
  }finally{s.w.close();}
 }
});

test("Read-only Devices has no dead intake form and healthy action accurately opens device evidence",async()=>{
 const s=await load({hash:"#devices",lang:"nl-NL"});try{
  assert.equal(s.doc.querySelector("#home-intake"),null);assert.equal(s.doc.querySelector('select[name="locale"]'),null);
  const healthy=[...s.doc.querySelectorAll(".home-device")].find(d=>d.textContent.includes("Friendly lamp 2"));
  assert.equal(healthy.querySelector("a").textContent,"Bekijk apparaatbewijs");
 }finally{s.w.close();}
});

test("Earlier real episode feedback is disclosed separately and unavailable check reason is visible",async()=>{
 const fixture=original["qa/earlier-episode"],id=fixture.problem.problem_id;
 assert.equal(fixture.feedback.length,0);assert.equal(fixture.earlier_feedback.length,1);
 const s=await load({hash:"#problems/"+id,mutate:v=>v["problems/"+id]=structuredClone(fixture)});try{
  const earlier=s.doc.querySelector("details.earlier-reports");assert.match(earlier.textContent,/First episode report only/);
  assert.equal(earlier.open,false);assert.equal(s.doc.querySelectorAll(".followthrough-grid > div:first-child > ol").length,0);
 }finally{s.w.close();}
 const missing=original["qa/check-unavailable"];
 const u=await load({hash:"#problems/"+id,mutate:v=>v["problems/"+id]=structuredClone(missing)});try{
  assert.match(u.doc.querySelector(".followthrough-grid").textContent,/Report saved; this device is no longer in the retained cohort/);
 }finally{u.w.close();}
});

test("Primary Settings and History shell follows Dutch locale while typed values and stored prose stay original",async()=>{
 const s=await load({hash:"#settings",mutate:v=>v["home/preferences"].locale="nl"});try{
  assert.match(s.doc.querySelector("#content").textContent,/Configuratie en privacy/);
  assert.match(s.doc.querySelector("#exception-form").textContent,/Reden.*Verloopt na uren.*Bewaar uitzondering/);
 }finally{s.w.close();}
 const h=await load({hash:"#history",mutate:v=>v["home/preferences"].locale="nl"});try{
  assert.match(h.doc.querySelector("#history-filter").textContent,/Onderdeel.*Zoeken.*Dag \(UTC\).*Zoek historie/);
  const option=h.doc.querySelector('select[name="kind"] option');assert.equal(option.textContent,"uitvoeringen");assert.equal(option.value,"runs");
 }finally{h.w.close();}
 const a=await load({hash:"#history/analyses",mutate:v=>{v["home/preferences"].locale="nl";v["history/page?kind=analyses"]={items:[{id:123,created:1,kind:"audit",provider:"mock",model:"mock",result:JSON.stringify({summary:"Configuration & privacy"})}],coverage:"Retained",next_cursor:null};}});try{
  assert.equal(a.doc.querySelector("tbody p").textContent,"Configuration & privacy");assert.equal(a.doc.querySelector("tbody a").textContent,"Open bevindingen en oorspronkelijk bewijs");
 }finally{a.w.close();}
});

test("Integration concentration is visible beside the chart without opening methodology",async()=>{
 const s=await load({mutate:v=>{Object.assign(v["today?window=24h"].metrics,{reliable_now:true,cache_state:"ready",cache_pending:false,cache_as_of:1000});v["today?window=24h"].metrics.integrations={items:[{platform:"zha",devices:2,offline:1,unknown:0,partial:0,points:[{end:1000,offline:1,unknown:0,partial:0,observed:2,coverage:1}]}],total:1};}});try{
  const strip=s.doc.querySelector(".home-integrations");assert.ok(strip);assert.equal(strip.closest("details"),null);
  assert.match(strip.textContent,/Zigbee \(ZHA\).*1 Unavailable signals.*2 devices in this snapshot/);assert.match(strip.textContent,/cause unknown/);
  assert.equal(strip.querySelector("a").hash,"#devices/reliability?platform=zha");assert.equal(strip.querySelector("svg").getAttribute("role"),"img");
 }finally{s.w.close();}
});

test("Actual initial unknown-coverage API offers a concrete manual coverage check without inventing a device problem",async()=>{
 const s=await load({lang:"nl-NL",mutate:v=>v["today?window=24h"]=structuredClone(v["qa/initial-limited"])});try{
  assert.match(s.doc.querySelector(".home-coverage-check").textContent,/Controleer of Vision verbonden is/);
  assert.equal(s.doc.querySelector(".home-coverage-check a").hash,"#overview");
  assert.equal(s.doc.querySelectorAll(".home-primary").length,1);assert.equal(s.doc.querySelectorAll(".home-priorities .today-priority").length,0);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
 }finally{s.w.close();}
});

test("Integration captions distinguish all-unknown, known zero, mixed, pending, failed and missing snapshots",async()=>{
 const cases=[
  {reliable_now:false,offline:0,partial:0,unknown:4,badge:true},
  {reliable_now:true,offline:0,partial:0,unknown:0,badge:false},
  {reliable_now:true,offline:1,partial:1,unknown:2,badge:false},
  {reliable_now:true,offline:0,partial:0,unknown:0,cache_pending:true,badge:true},
  {reliable_now:true,offline:0,partial:0,unknown:0,cache_state:"failed",badge:true},
  {reliable_now:true,offline:0,partial:0,unknown:0,cache_as_of:null,badge:true},
 ];
 const texts=[];
 for(const scene of cases){
  const s=await load({lang:"nl-NL",mutate:v=>{
   const d=v["today?window=24h"].metrics;
   Object.assign(d,{cache_state:"ready",cache_pending:false,cache_as_of:1000},scene);
   d.integrations={items:[{platform:"zha",devices:4,offline:scene.offline,partial:scene.partial,unknown:scene.unknown,points:[{end:1000,offline:scene.offline,partial:scene.partial,unknown:scene.unknown,observed:4,coverage:scene.reliable_now?1:0}]}],total:1};
  }});try{
   const strip=s.doc.querySelector(".home-integrations"),text=strip.textContent;texts.push(text);
   assert.equal(text.includes("Actuele beschikbaarheid is onbekend"),scene.badge);
   assert.match(text,/Bewaarde momentopname/);assert.doesNotMatch(text,/0 \/ 4/);
   if(scene.cache_as_of!==null){
    assert.match(text,new RegExp(scene.unknown+" niet beoordeeld"));
    assert.match(text,new RegExp(scene.partial+" Deels niet beschikbaar"));
    assert.match(text,/4 apparaten in deze momentopname/);
   }else assert.doesNotMatch(strip.querySelector(".heatmap-row > small").textContent,/0 Signalen/);
   if(scene.cache_pending)assert.match(text,/Momentopname wordt bijgewerkt/);
   if(scene.cache_state==="failed")assert.match(text,/Verversen van momentopname mislukt/);
  }finally{s.w.close();}
 }
 assert.notEqual(texts[0],texts[1]);
});

test("Foreground intake cancellation scrolls the main route into view while background refresh preserves scroll and focus",async()=>{
 const scrolls=[];
 const s=await load({hash:"#intake",setup:w=>{w.HTMLElement.prototype.scrollIntoView=function(options){scrolls.push({id:this.id,options});w.__simulatedScroll=0;};}});try{
  const main=s.doc.querySelector("#main"),before=scrolls.length;
  main.scrollTop=600;s.w.__simulatedScroll=600;
  const choice=s.doc.querySelector('[data-field="known_issue"]');choice.checked=true;event(s.w,choice,"change");
  click(s.w,"#home-cancel");await until(()=>s.w.location.hash==="#today"&&s.doc.querySelector(".home-primary"));
  assert.equal(scrolls.length,before+1);assert.equal(scrolls.at(-1).id,"main");
  assert.deepEqual(JSON.parse(JSON.stringify(scrolls.at(-1).options)),{block:"start",behavior:"auto"});
  assert.equal(main.scrollTop,0);assert.equal(s.w.__simulatedScroll,0);assert.equal(s.doc.activeElement,main);
  assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
  const after=scrolls.length;main.scrollTop=450;s.w.__simulatedScroll=450;
  await s.w.__renderHome({background:true});assert.equal(scrolls.length,after);assert.equal(main.scrollTop,450);assert.equal(s.w.__simulatedScroll,450);
  click(s.w,".home-primary");await until(()=>s.doc.querySelector("#home-feedback"));
  const input=s.doc.querySelector("textarea");input.value="Keep my draft";input.focus();main.scrollTop=350;s.w.__simulatedScroll=350;
  const typed=scrolls.length;await s.w.__renderHome({background:true});
  assert.equal(scrolls.length,typed);assert.equal(s.doc.activeElement,input);assert.equal(input.value,"Keep my draft");assert.equal(main.scrollTop,350);assert.equal(s.w.__simulatedScroll,350);
 }finally{s.w.close();}
});

test("Initial asynchronous rendering leaves body or an already chosen control focused",async()=>{
 for(const selected of [false,true]){
  const scrolls=[];
  const s=await load({setup:w=>{
   w.HTMLElement.prototype.scrollIntoView=function(){scrolls.push(this.id);};
   if(selected){const button=w.document.createElement("button");button.id="chosen-control";button.textContent="Chosen control";w.document.body.append(button);button.focus();}
  }});try{
   assert.equal(s.doc.activeElement,selected?s.doc.querySelector("#chosen-control"):s.doc.body);
   assert.equal(scrolls.length,selected?0:1);
   if(!selected)assert.deepEqual(scrolls,["main"]);
  }finally{s.w.close();}
 }
});

test("Unavailable locale preferences are cosmetic on primary and expert routes and a later read can retry",async()=>{
 for(const hash of ["#today","#problems","#devices","#intake","#settings","#history","#overview","#automations"]){
  const state={fail:true};
  const s=await load({hash,lang:"nl-NL",preferencesState:state,mutate:v=>{v["home/preferences"].locale="en";v["today?window=24h"].preferences.locale="auto";}});try{
   assert.equal(s.doc.documentElement.lang,"nl");assert.ok(s.doc.querySelector("#content").children.length);
   assert.doesNotMatch(s.doc.querySelector("#content").textContent,/Unable to load current observations/);
   assert.equal(s.calls.filter(c=>c.method==="POST").length,0);
   state.fail=false;
   if(hash==="#today")s.values["today?window=24h"].preferences.locale="en";
   await s.w.__renderHome();assert.equal(s.doc.documentElement.lang,"en");
   assert.ok(s.calls.filter(c=>c.path==="home/preferences").length>=2);
  }finally{s.w.close();}
 }
});

test("Shell translation is restricted to owned labels and detects copy drift without rewriting user words",async()=>{
 const s=await load({hash:"#settings",lang:"nl-NL",mutate:v=>{
  v.settings.owner_value="Source";v.exceptions=[{entity_id:"light.local_0",reason:"Search",expires:1000}];
 }});try{
  const content=s.doc.querySelector("#content");
  assert.match(content.textContent,/Stel providersleutels, modellen, toestemming/);
  assert.match(content.textContent,/Budgetuitwijking vereist aparte toestemming/);
  assert.match(content.textContent,/Verminder aandacht voor verwachte beschikbaarheidswaarnemingen/);
  assert.match(content.textContent,/Actuele configuratie \(zonder geheimen\)/);
  assert.ok([...content.querySelectorAll("dd")].some(n=>n.textContent==="Source"));
  assert.ok([...content.querySelectorAll("td")].some(n=>n.textContent==="Search"));
  const fixture=s.doc.createElement("div");fixture.innerHTML='<p class="user-reason">Search</p><select><option>Reason</option></select><summary>Source</summary><span data-home-shell>Search history</span>';
  s.w.VisionHome.localizeShell("settings",fixture);
  assert.equal(fixture.querySelector("p").textContent,"Search");assert.equal(fixture.querySelector("option").textContent,"Reason");
  assert.equal(fixture.querySelector("option").value,"Reason");assert.equal(fixture.querySelector("summary").textContent,"Source");
  assert.equal(fixture.querySelector("[data-home-shell]").textContent,"Zoek historie");
 }finally{s.w.close();}
});

test("Successful intake and Settings language saves prefill a same-window rerun and survive device-only saves",async()=>{
 for(const origin of ["#intake","#settings"]){
  const s=await load({hash:origin,lang:"en",mutate:v=>v["home/preferences"].locale="auto"});try{
   if(origin==="#intake"){
    const select=s.doc.querySelector('[name="locale"]');select.value="nl";event(s.w,select,"change");
    click(s.w,'button[value="complete"]');await until(()=>s.w.location.hash==="#today"&&s.doc.querySelector(".home-primary"));
   }else{
    click(s.w,'[data-home-locale="nl"]');await until(()=>s.doc.documentElement.lang==="nl");
   }
   s.w.location.hash="#intake";await until(()=>s.doc.querySelector("#home-intake"));
   assert.equal(s.doc.querySelector('[name="locale"]').value,"nl");
   const known=s.doc.querySelector('[data-field="known_issue"]');known.checked=true;event(s.w,known,"change");
   click(s.w,'button[value="draft"]');await until(()=>s.w.location.hash==="#today"&&s.doc.querySelector(".home-primary"));
   const writes=s.calls.filter(c=>c.method==="POST"&&c.path==="home/preferences");
   assert.equal(writes.length,2);assert.equal(writes[0].body.locale,"nl");assert.equal(Object.hasOwn(writes[1].body,"locale"),false);
   assert.equal(s.values["home/preferences"].locale,"nl");assert.equal(s.doc.documentElement.lang,"nl");
   s.w.location.hash="#intake";await until(()=>s.doc.querySelector("#home-intake"));
   assert.equal(s.doc.querySelector('[name="locale"]').value,"nl");
  }finally{s.w.close();}
 }
});

test("Device-only intake save preserves server language through a failed preferences read or another-window change",async()=>{
 for(const unavailable of [false,true]){
  const state={fail:unavailable};
  const s=await load({hash:"#intake",lang:"en",preferencesState:state,mutate:v=>v["home/preferences"].locale=unavailable?"nl":"auto"});try{
   assert.equal(s.doc.querySelector('[name="locale"]').value,"auto");
   // A real read failure, or a newer server choice not represented by this cached form.
   s.values["home/preferences"].locale="nl";s.values["today?window=24h"].preferences.locale="nl";
   const known=s.doc.querySelector('[data-field="known_issue"]');known.checked=true;event(s.w,known,"change");
   click(s.w,'button[value="complete"]');await until(()=>s.w.location.hash==="#today"&&s.doc.querySelector(".home-primary"));
   const request=s.calls.find(c=>c.method==="POST");assert.equal(Object.hasOwn(request.body,"locale"),false);
   assert.equal(s.values["home/preferences"].locale,"nl");assert.equal(s.doc.documentElement.lang,"nl");
   state.fail=false;s.w.location.hash="#intake";await until(()=>s.doc.querySelector("#home-intake"));
   assert.equal(s.doc.querySelector('[name="locale"]').value,"nl");
  }finally{s.w.close();}
 }
});

test("A failed preferences POST preserves the prior locale cache and dirty intake edits for retry",async()=>{
 const state={postFailures:1};
 const s=await load({hash:"#intake",lang:"en",preferencesState:state,mutate:v=>v["home/preferences"].locale="auto"});try{
  const select=s.doc.querySelector('[name="locale"]');select.value="nl";event(s.w,select,"change");
  const known=s.doc.querySelector('[data-field="known_issue"]');known.checked=true;event(s.w,known,"change");
  click(s.w,'button[value="draft"]');await until(()=>s.doc.querySelector("#notice").textContent.includes("Synthetic preferences save failed"));
  assert.equal(s.w.location.hash,"#intake");assert.equal(s.values["home/preferences"].locale,"auto");assert.equal(s.doc.documentElement.lang,"en");
  assert.equal((await s.w.VisionHome.resolveLocale()).locale,"auto");
  await s.w.__renderHome();assert.equal(s.doc.querySelector('[name="locale"]').value,"nl");assert.equal(s.doc.querySelector('[data-field="known_issue"]').checked,true);
  click(s.w,'button[value="draft"]');await until(()=>s.w.location.hash==="#today"&&s.doc.querySelector(".home-primary"));
  const writes=s.calls.filter(c=>c.method==="POST");assert.deepEqual(writes[1].body,writes[0].body);
  assert.equal(s.values["home/preferences"].locale,"nl");
 }finally{s.w.close();}
});

test("Personal saves and intake Skip also replace the cached preferences with the confirmed response",async()=>{
 for(const origin of ["personal","skip"]){
  const id=original["problems?mode=attention&page=1"].items[0].problem_id;
  const s=await load({hash:origin==="personal"?"#problems/"+id:"#intake",lang:"en",mutate:v=>v["home/preferences"].locale="auto"});try{
   s.values["home/preferences"].locale="nl";s.values["today?window=24h"].preferences.locale="nl";
   if(origin==="personal"){
    const control=s.doc.querySelector('#home-personal [name="importance"]');control.value="high";event(s.w,control,"change");
    event(s.w,s.doc.querySelector("#home-personal"),"submit");await until(()=>s.doc.documentElement.lang==="nl");
   }else{
    click(s.w,"#home-skip");await until(()=>s.w.location.hash==="#today"&&s.doc.querySelector(".home-primary"));
   }
   assert.equal(Object.hasOwn(s.calls.find(c=>c.method==="POST").body,"locale"),false);
   s.w.location.hash="#intake";await until(()=>s.doc.querySelector("#home-intake"));
   assert.equal(s.doc.querySelector('[name="locale"]').value,"nl");
  }finally{s.w.close();}
 }
});
