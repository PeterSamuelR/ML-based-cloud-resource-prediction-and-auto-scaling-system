import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(process.cwd());
const skillDir = "C:/Users/psamu/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations";
const sourcePath = "C:/Users/psamu/OneDrive/Desktop/Second_Review_ML_Cloud_Autoscaling.pptx";
const buildDir = path.join(workspaceDir, ".ppt-build");
const finalPath = path.join(workspaceDir, "review2-output", "Second_Review_ML_Cloud_Autoscaling_Improved_v3.pptx");
const runtimePython = "C:/Users/psamu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const { resolvePresentationFont, applyPresentationChartFont, finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools/artifact_tool_utils.mjs")).href);

const font = resolvePresentationFont({ fontFamily: "Arial" });
const C = { navy: "#1F4E79", blue: "#2F75B5", lightBlue: "#D9EAF7", green: "#548235", paleGreen: "#E2F0D9", amber: "#C55A11", paleAmber: "#FCE4D6", red: "#C00000", paleRed: "#FDE9E7", text: "#1F2937", muted: "#5B6573", line: "#C9D3DD", pale: "#F7F9FB", white: "#FFFFFF" };
const slideW = 1280, slideH = 720;

function box(slide, text, x, y, w, h, opts = {}) {
  const s = slide.shapes.add({ geometry: opts.geometry ?? "textbox", position: { left: x, top: y, width: w, height: h }, fill: opts.fill ?? "none", line: opts.line ?? { fill: "none", width: 0 }, borderRadius: opts.radius, name: opts.name });
  s.text = text;
  s.text.style = { typeface: font, fontSize: opts.size ?? 18, color: opts.color ?? C.text, bold: opts.bold ?? false, alignment: opts.align ?? "left", verticalAlignment: opts.valign ?? "middle", autoFit: "shrinkText", breakLine: false };
  return s;
}
function rect(slide, x, y, w, h, fill, opts = {}) { const geometry=opts.geometry ?? "roundRect"; return slide.shapes.add({ geometry, position: { left: x, top: y, width: w, height: h }, fill, line: opts.line ?? { style: "solid", fill: opts.stroke ?? fill, width: opts.width ?? 0.8 }, ...(geometry === "rect" || geometry === "textbox" || geometry === "roundRect" ? {borderRadius:opts.radius ?? "rounded-md"} : {}), shadow: opts.shadow }); }
function title(slide, text, subtitle = "") {
  slide.background.fill = C.white;
  box(slide, text, 43, 25, 1190, 42, { size: 25, bold: true, color: C.navy });
  rect(slide, 43, 75, 1180, 4, C.blue, { geometry: "rect", line: { fill: "none", width: 0 } });
  if (subtitle) box(slide, subtitle, 43, 83, 1180, 25, { size: 12, color: C.muted });
}
function caption(slide, text, x, y, w) { box(slide, text, x, y, w, 24, { size: 12, color: C.muted, align: "center" }); }
function label(slide, text, x, y, w, color=C.blue) { rect(slide,x,y,w,25,color,{radius:"rounded-full",line:{fill:"none",width:0}}); box(slide,text,x,y,w,25,{size:11,bold:true,color:C.white,align:"center"}); }
function arrow(slide, a, b, sides = ["right","left"], color=C.blue, kind="straight") { const connector=slide.shapes.connect(a,b,{kind,fromSide:sides[0],toSide:sides[1],line:{style:"solid",fill:color,width:1.8},tail:{type:"triangle",width:"sm",length:"sm"}}); connector.sendToBack(); }
function addTable(slide, values, x, y, w, h, headerColor=C.navy, fontSize=13) {
  const table = slide.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,values});
  table.styleOptions = { headerRow:true, bandedRows:true };
  table.borders.assign({style:"solid",fill:C.line,width:0.75});
  for(let c=0;c<values[0].length;c++) { const cell=table.getCell(0,c); cell.fill=headerColor; cell.text.style={typeface:font,fontSize,bold:true,color:C.white,alignment:"center"}; }
  for(let r=1;r<values.length;r++) for(let c=0;c<values[0].length;c++) { const cell=table.getCell(r,c); cell.fill=(r%2?C.white:C.pale); cell.text.style={typeface:font,fontSize,color:C.text,alignment:c===0?"left":"center"}; }
  return table;
}
function moduleCard(slide, n, name, content, x, y, w, h, accent) {
  rect(slide,x,y,w,h,C.white,{stroke:C.line,width:1,shadow:"shadow-sm"});
  rect(slide,x+16,y+15,38,38,accent,{geometry:"ellipse",line:{fill:"none",width:0}});
  box(slide,String(n),x+16,y+15,38,38,{size:18,bold:true,color:C.white,align:"center"});
  box(slide,name,x+66,y+15,w-82,38,{size:17,bold:true,color:C.navy});
  box(slide,content,x+20,y+66,w-40,h-82,{size:14,color:C.text});
}

const deck = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
for (let i = deck.slides.items.length - 1; i >= 1; i--) deck.slides.getItem(i).delete();
const slides = Array.from({length:8}, () => deck.slides.add());
// Slide 2
{ const s=slides[0]; title(s,"OBJECTIVES & ABSTRACT");
  label(s,"OBJECTIVES",43,104,130,C.blue); label(s,"ABSTRACT",660,104,120,C.green);
  const objectives=["Monitor resource utilisation and workload for healthy container replicas.","Predict future aggregate CPU utilisation with Random Forest regression.","Apply reactive and predictive scaling within configured replica limits.","Maintain safe Nginx membership for labelled Docker replicas.","Detect persistent forecast errors and retrain only after validation.","Evaluate policies under controlled workload patterns."];
  rect(s,43,142,565,500,C.pale,{stroke:C.line});
  objectives.forEach((v,i)=>{rect(s,65,166+i*59,18,18,C.blue,{geometry:"ellipse",line:{fill:"none",width:0}});box(s,"✓",65,166+i*59,18,18,{size:12,bold:true,color:C.white,align:"center"});box(s,v,96,160+i*59,480,34,{size:16,color:C.text});});
  rect(s,660,142,563,500,"#F8FBF8",{stroke:"#C8DEC2"});
  box(s,"This project implements a Docker-based framework for comparing reactive, predictive, and error-aware adaptive predictive autoscaling. Locust sends controlled traffic through Nginx to healthy FastAPI replicas. The monitoring pipeline stores five-second CPU, memory, request-rate, response-time, and replica measurements in MongoDB. A Random Forest regression model predicts aggregate CPU 30 seconds ahead using only information available at the prediction time. The controller records prediction feedback and can retrain a candidate model after persistent errors, subject to chronological validation before activation.",694,175,495,250,{size:17,color:C.text});
  rect(s,694,456,495,116,C.paleGreen,{stroke:"#A9D18E"}); box(s,"Primary target",718,474,180,20,{size:14,bold:true,color:C.green}); box(s,"Future aggregate CPU utilisation\nArithmetic mean across active healthy replicas",718,498,440,52,{size:17,bold:true,color:C.navy});
  box(s,"Measurement contract: 5-second monitoring interval   |   30-second prediction horizon",694,590,495,28,{size:13,color:C.muted,align:"center"}); }
// Slide 3
{ const s=slides[1]; title(s,"EXISTING & PROPOSED ARCHITECTURE","The proposed design closes the loop from workload generation to validated model adaptation");
  label(s,"EXISTING REACTIVE PATH",43,110,205,C.amber); const ex=["User / workload","Application","Resource monitoring","Threshold decision","Scale out / in"]; let prev=null; ex.forEach((t,i)=>{const node=rect(s,43,151+i*76,200,43,C.paleAmber,{stroke:"#E9B88E"});box(s,t,43,151+i*76,200,43,{size:15,bold:true,color:C.amber,align:"center"});if(prev)arrow(s,prev,node,["bottom","top"],C.amber);prev=node;});
  label(s,"PROPOSED CONTROL LOOP",281,110,190,C.blue); const prop=["Locust","Nginx load balancer","Healthy FastAPI replicas","Monitoring","MongoDB","Random Forest prediction","Scaling policy","Docker replica management","Nginx membership update"]; let nodes=[]; prop.forEach((t,i)=>{const node=rect(s,286,145+i*49,360,34,i===2?C.lightBlue:C.white,{stroke:C.blue});box(s,t,286,145+i*49,360,34,{size:14,bold:i===2||i===5||i===6,color:C.navy,align:"center"});if(nodes.length)arrow(s,nodes[nodes.length-1],node,["bottom","top"],C.blue);nodes.push(node);});
  const api=rect(s,286,610,360,42,C.paleGreen,{stroke:"#A9D18E"});box(s,"React dashboard  ↔  Backend APIs",286,610,360,42,{size:15,bold:true,color:C.green,align:"center"});
  label(s,"ERROR-AWARE ADAPTIVE LOOP",692,110,240,C.green); const adap=["Actual CPU","Prediction error","Persistent error detection","Candidate retraining","Chronological validation","Model activation"]; let ap=[]; adap.forEach((t,i)=>{const node=rect(s,760,146+i*68,300,42,C.paleGreen,{stroke:"#A9D18E"});box(s,t,760,146+i*68,300,42,{size:15,bold:i===2||i===4||i===5,color:C.green,align:"center"});if(ap.length)arrow(s,ap[ap.length-1],node,["bottom","top"],C.green);ap.push(node);}); arrow(s,nodes[3],ap[0],["right","left"],C.green,"elbow"); box(s,"Validated candidate version becomes the active predictor",770,610,275,28,{size:12,color:C.green,align:"center"});
  box(s,"Scale-in safety: remove from Nginx upstream → validate configuration → graceful reload → stop replica",692,575,500,36,{size:13,color:C.muted,align:"center"}); }
// Slide 4
{ const s=slides[2]; title(s,"MODULE DESCRIPTION");
  moduleCard(s,1,"Workload generation","Locust scenarios: stable, gradual increase, sudden spike, sudden drop, periodic, and changing workload.\n\nTraffic enters only through Nginx.",43,111,370,245,C.blue);
  moduleCard(s,2,"Monitoring & data management","Five-second sampling of labelled healthy replicas.\n\nCPU, memory, request rate, response time, replica count, and timestamps persist in MongoDB.",455,111,370,245,C.green);
  moduleCard(s,3,"ML prediction","Leak-free dataset construction.\n\nRandom Forest predicts aggregate CPU 30 seconds ahead. Chronological validation reports MAE and RMSE.",867,111,370,245,"#8064A2");
  moduleCard(s,4,"Autoscaling & adaptation","Reactive and predictive decisions use configured thresholds, cooldowns, and replica limits.\n\nPersistent error gates candidate retraining and validation.",250,404,370,245,C.amber);
  moduleCard(s,5,"Dashboard & experimentation","React dashboard exposes read-only live state and histories.\n\nExperiment runner records raw observations and exports CSV/JSON.",662,404,370,245,"#5B9BD5"); }
// Slide 5
{ const s=slides[3]; title(s,"STATUS SINCE REVIEW 1");
  box(s,"Implemented and verified",43,102,520,28,{size:18,bold:true,color:C.green}); box(s,"Current final-stage work",640,102,540,28,{size:18,bold:true,color:C.amber});
  const done=["System architecture","FastAPI application","Docker containerization","Nginx load balancing","Dynamic replica membership","Monitoring pipeline","MongoDB integration","ML prediction model","Reactive scaling","Predictive scaling","Adaptive retraining","React dashboard","Experiment framework","Evaluation experiments"];
  rect(s,43,140,540,490,"#F8FBF8",{stroke:"#A9D18E"}); done.forEach((v,i)=>{const y=158+i*32;rect(s,64,y,18,18,C.green,{geometry:"ellipse",line:{fill:"none",width:0}});box(s,"✓",64,y,18,18,{size:12,bold:true,color:C.white,align:"center"});box(s,v,94,y-3,405,25,{size:15,color:C.text});box(s,"COMPLETED",474,y-2,88,22,{size:10,bold:true,color:C.green,align:"center"});});
  const current=["Final result analysis","Final report and documentation","Demo refinement","Presentation preparation","Viva preparation","Final validation"];
  rect(s,640,140,540,490,"#FFFCF5",{stroke:"#F4B183"}); current.forEach((v,i)=>{const y=164+i*61;rect(s,664,y,22,22,C.amber,{geometry:"ellipse",line:{fill:"none",width:0}});box(s,String(i+1),664,y,22,22,{size:12,bold:true,color:C.white,align:"center"});box(s,v,704,y-2,300,28,{size:17,color:C.text});box(s,"ONGOING",1030,y-1,112,25,{size:11,bold:true,color:C.amber,align:"center"});});
  box(s,"The prototype, data pipeline, policies, dashboard, and fixed evaluation matrix are complete. The remaining work prepares the final analysis, documentation, and demonstration.",640,550,500,54,{size:15,color:C.muted}); }
// Slide 6
{ const s=slides[4]; title(s,"CURRENT IMPLEMENTATION","Live local evidence captured from the running project environment"); const dashboard=await fs.readFile(path.join(buildDir,"assets","dashboard-live.png"));
  rect(s,43,112,740,435,C.pale,{stroke:C.line,shadow:"shadow-sm"}); s.images.add({blob:dashboard,contentType:"image/png",alt:"Live project dashboard screenshot",fit:"cover",position:{left:54,top:123,width:718,height:404},geometry:"roundRect",borderRadius:"rounded-md"}); caption(s,"Live control-loop dashboard: observed status, CPU, predictions, model version, and validation metrics",53,552,720);
  rect(s,817,112,405,200,C.white,{stroke:C.line,shadow:"shadow-sm"}); box(s,"Docker Compose service status",842,132,350,25,{size:18,bold:true,color:C.navy}); const services=[["Service","State"],["Application replica","Healthy"],["MongoDB","Healthy"],["Backend API","Running"],["Frontend dashboard","Running"],["Nginx","Running"],["Membership controller","Running"]]; const t=addTable(s,services,842,164,350,126,C.navy,11); for(let r=1;r<services.length;r++){t.getCell(r,1).text.style={typeface:font,fontSize:11,bold:true,color:C.green,alignment:"center"};}
  rect(s,817,342,405,205,"#F8FBF8",{stroke:"#C8DEC2"}); box(s,"Implementation evidence",842,362,350,25,{size:18,bold:true,color:C.navy}); box(s,"• FastAPI application replicas expose /health and /work\n• Nginx routes traffic only to healthy labelled replicas\n• Backend records observations and read-only APIs\n• React dashboard polls the API every five seconds\n• Repository is organised into app, backend, nginx, load-tests, config, docs, results",842,399,335,125,{size:14,color:C.text});
  box(s,"No pre-existing Locust or terminal screenshots were stored in the repository. This slide therefore uses the verified live dashboard and live Compose service state rather than stock or recreated images.",54,615,1130,32,{size:12,color:C.muted,align:"center"}); }
// Slide 7
{ const s=slides[5]; title(s,"PRELIMINARY RESULTS & TESTING","Recorded final evaluation matrix: 15 valid policy–workload trials; fixed traces did not trigger scaling");
  const chart=s.charts.add("bar",{position:{left:43,top:115,width:660,height:300},categories:["Stable","Gradual","Spike","Drop","Changing"],series:[{name:"Reactive",values:[11.983,14.018,12.428,7.919,15.531],fill:C.blue},{name:"Predictive",values:[15.933,12.424,7.147,12.715,9.649],fill:C.green},{name:"Adaptive predictive",values:[16.161,14.812,11.073,12.955,11.435],fill:"#8064A2"}],barOptions:{direction:"column",grouping:"clustered",gapWidth:55},hasLegend:true,legend:{position:"bottom",textStyle:{typeface:font,fontSize:12}},yAxis:{title:"Prediction MAE (CPU percentage points)",min:0,max:20,majorUnit:5,textStyle:{typeface:font,fontSize:11},majorGridlines:{style:"solid",fill:"#D9E2F3",width:1}},xAxis:{textStyle:{typeface:font,fontSize:11}},chartFill:C.white,plotAreaFill:C.white}); applyPresentationChartFont(chart,{fontFamily:font});
  const sums=[["Policy","Trials","MAE range","Response-time range","Scaling events","Adaptation attempts"],["Reactive","5","7.919–15.531","116.073–175.784 ms","0","0"],["Predictive","5","7.147–15.933","115.709–118.278 ms","0","0"],["Adaptive predictive","5","11.073–16.161","114.434–117.595 ms","0","1"]]; addTable(s,sums,731,115,492,205,C.navy,11);
  const resultShot=await fs.readFile(path.join(buildDir,"assets","dashboard-results-live.png")); rect(s,731,340,492,192,C.pale,{stroke:C.line}); s.images.add({blob:resultShot,contentType:"image/png",alt:"Live dashboard result screenshot",fit:"cover",position:{left:741,top:350,width:472,height:172},geometry:"roundRect",borderRadius:"rounded-md"}); caption(s,"Live dashboard view of observed metrics and prediction feedback",741,535,472);
  rect(s,43,450,660,151,C.paleAmber,{stroke:"#E9B88E"}); box(s,"Reporting note",65,468,180,23,{size:17,bold:true,color:C.amber}); box(s,"All chart and table values come from results/final-evaluation-valid-matrix.csv and .json. The 15 fixed evaluation traces recorded zero scaling events. Separate controlled validation verified scaling and adaptive candidate handling. No performance improvement is claimed from this matrix.",65,497,610,77,{size:15,color:C.text});
  box(s,"Model version recorded for every final-matrix trial: rf-20260917180253-f01e3afc",43,620,1180,24,{size:12,color:C.muted,align:"center"}); s.speakerNotes.text="Sources: results/final-evaluation-valid-matrix.csv and results/final-evaluation-valid-matrix.json. Values are recorded observations; no comparative inference is made."; }
// Slide 8
{ const s=slides[6]; title(s,"HURDLES & MITIGATION"); const vals=[["Hurdle","Mitigation"],["Docker / WSL environment setup","Used a reproducible Docker Compose environment and project-scoped labels to keep application control separate from unrelated containers."],["Dynamic Nginx replica management","Membership controller discovers only healthy labelled replicas, generates an upstream, validates Nginx, then reloads gracefully."],["Prediction and target-time alignment","Locked the 30-second horizon and five-second sampling interval; dataset and feedback use chronological target matching."],["Persistent prediction errors","Adaptive service requires threshold breaches across consecutive evaluated predictions before candidate retraining."],["Candidate model replacement","Candidate model must pass chronological validation before activation; rejected and superseded versions remain recorded."],["Windows command-length limitation","Experiment recorder accepts encoded input through standard input, avoiding oversized command-line payloads."]]; const table=addTable(s,vals,43,118,1180,450,"#385723",14); table.columnWidths=[325,855]; for(let r=1;r<vals.length;r++){table.getCell(r,0).text.style={typeface:font,fontSize:14,bold:true,color:C.navy,alignment:"left"};table.getCell(r,1).text.style={typeface:font,fontSize:14,color:C.text,alignment:"left"};}
  rect(s,43,605,1180,45,C.paleGreen,{stroke:"#A9D18E"}); box(s,"All mitigations describe implemented behaviour or recorded integration issues. They do not claim production-cloud readiness.",60,614,1146,24,{size:14,bold:true,color:C.green,align:"center"}); }
// Slide 9
{ const s=slides[7]; title(s,"FUTURE WORK & TIMELINE","Remaining delivery work and possible technical extensions");
  label(s,"REMAINING DELIVERY WORK",43,110,210,C.amber); const work=["Final result analysis","Final report / documentation","Demo refinement","Presentation preparation","Viva preparation","Final validation"]; work.forEach((v,i)=>{box(s,v,43,153+i*48,220,28,{size:15,color:C.text});});
  const weeks=["W1","W2","W3","W4","W5","W6"]; weeks.forEach((w,i)=>{box(s,w,425+i*110,121,80,22,{size:13,bold:true,color:C.navy,align:"center"});rect(s,425+i*110,145,1,305,C.line,{geometry:"rect",line:{fill:"none",width:0}});}); const bars=[[0,2,C.blue],[1,3,C.green],[2,4,C.amber],[3,5,"#8064A2"],[4,5,"#5B9BD5"],[5,6,C.green]]; bars.forEach(([start,end,color],i)=>{rect(s,425+start*110,154+i*48,(end-start)*110-9,26,color,{line:{fill:"none",width:0},radius:"rounded-sm"});});
  label(s,"POSSIBLE TECHNICAL EXTENSIONS",43,478,245,C.blue); const ext=["Integrate Locust controls into the dashboard","Run longer and higher-intensity workload experiments","Compare additional prediction models","Improve dashboard visualisation and experiment controls","Explore cloud or Kubernetes deployment as future work"]; ext.forEach((v,i)=>{rect(s,55,520+i*28,10,10,C.blue,{geometry:"ellipse",line:{fill:"none",width:0}});box(s,v,78,512+i*28,520,25,{size:14,color:C.text});});
  rect(s,675,490,505,136,"#F8FBF8",{stroke:C.line}); box(s,"Timeline interpretation",700,512,440,25,{size:18,bold:true,color:C.navy});box(s,"The timeline sequences final analysis, documentation, demonstration, presentation, viva preparation, and final validation. Week labels are planning markers, not completed milestones.",700,548,440,54,{size:15,color:C.text}); }

const candidatePath = path.join(buildDir, "candidate-review2.pptx");
await (await PresentationFile.exportPptx(deck)).save(candidatePath);
await fs.mkdir(path.dirname(finalPath), {recursive:true});
const requirements = { explicitTotalSlideCount:9, requiredNativeTableOwnerSlides:[7,8], requiredNativeChartOwnerSlides:[7], materializeLiteralChartWorkbooks:true, sourceTemplatePath:sourcePath, fontPolicy:{basis:"reference",families:["Arial","Times New Roman"],referencePath:sourcePath,referenceSha256:"3c4aaa321507c3c04070399fb10b95dd5acc6f6c614fdbf45b4236ea0e0f8535"} };
await finalizePresentation({ ...requirements, workspaceDir, candidatePath, finalPath, pythonExecutable:runtimePython, integrityValidatorPath:path.join(skillDir,"container_tools","inspect_presentation_package_integrity.py"), layoutValidatorPath:path.join(skillDir,"container_tools","inspect_presentation_layout_geometry.py"), layoutArgs:["--expected-slide-size-emu","12192000,6858000","--validate-bullet-geometry","--validate-heading-fit","--require-native-table-slide","7","--require-native-table-slide","8"], requiredNativeTableOwnerSlides:[7,8], fontPolicy:requirements.fontPolicy, verifyArtifactToolImport:true, receiptPath:path.join(buildDir,"review2-v3-validation.json") });
console.log(finalPath);
