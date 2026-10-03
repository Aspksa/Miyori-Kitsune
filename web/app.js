const pages={chat:"Miyori Kitsune",workspace:"Рабочее пространство",home:"Домашнее пространство",settings:"Настройки",updates:"Обновление проекта",account:"Личный кабинет",mobile:"Мобильное приложение"};
const sidebar=document.getElementById("sidebar");
const scrim=document.getElementById("mobileScrim");
const title=document.getElementById("pageTitle");
const navItems=[...document.querySelectorAll(".nav-item[data-page]")];

function closeMenu(){sidebar.classList.remove("open");scrim.classList.remove("show");}
function openPage(name){
  document.querySelectorAll(".page").forEach(el=>el.classList.remove("active"));
  navItems.forEach(el=>el.classList.toggle("active",el.dataset.page===name));
  const page=document.getElementById("page-"+name);
  if(page){page.classList.add("active");title.textContent=pages[name]||"Miyori Kitsune";history.replaceState(null,"","#"+name);}
  closeMenu();window.scrollTo({top:0,behavior:"smooth"});
}
navItems.forEach(button=>button.addEventListener("click",()=>openPage(button.dataset.page)));
document.getElementById("menuButton").addEventListener("click",()=>{sidebar.classList.add("open");scrim.classList.add("show");});
scrim.addEventListener("click",closeMenu);
window.addEventListener("keydown",event=>{if(event.key==="Escape")closeMenu();});

document.querySelectorAll("[data-prompt]").forEach(button=>button.addEventListener("click",()=>{openPage("chat");const prompt=document.getElementById("prompt");prompt.value=button.dataset.prompt;prompt.focus();prompt.dispatchEvent(new Event("input"));}));

const prompt=document.getElementById("prompt");
prompt.addEventListener("input",()=>{prompt.style.height="auto";prompt.style.height=Math.min(prompt.scrollHeight,180)+"px";});
prompt.addEventListener("keydown",event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();document.getElementById("composer").requestSubmit();}});
let chatBusy=false;
let pendingBrainRequest=null;
let chatSessionId=null;
let chatSessions=[];
let thinkingTimer=null;

function chatEscape(value){return String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch]));}
function chatTime(){return new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});}

function sessionTime(ts){
  if(!ts)return "";
  const date=new Date(ts*1000),now=new Date();
  return date.toDateString()===now.toDateString()?date.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"}):date.toLocaleDateString();
}

function renderChatHistory(){
  const root=document.getElementById("chatHistoryList");
  if(!root)return;
  if(!chatSessions.length){root.innerHTML='<p class="empty-state">Диалогов пока нет.</p>';return;}
  root.innerHTML=chatSessions.map(session=>{
    const active=session.id===chatSessionId?" active":"";
    return '<div class="chat-history-row'+active+'" data-chat-session="'+chatEscape(session.id)+'"><button class="chat-history-open" type="button"><b>'+chatEscape(session.title||"Новый диалог")+'</b><small>'+chatEscape(session.preview||"Пустой диалог")+'</small></button><div class="chat-history-meta"><span>'+chatEscape(sessionTime(session.updated_at))+'</span><button type="button" data-chat-menu title="Действия">•••</button></div></div>';
  }).join("");
  root.querySelectorAll("[data-chat-session]").forEach(row=>{
    row.querySelector(".chat-history-open").addEventListener("click",()=>openChatSession(row.dataset.chatSession));
    row.querySelector("[data-chat-menu]").addEventListener("click",event=>{
      event.stopPropagation();
      const session=chatSessions.find(x=>x.id===row.dataset.chatSession);
      if(!session)return;
      const action=window.prompt("Введите новое название. Чтобы удалить диалог, введите: удалить",session.title||"");
      if(action===null)return;
      if(action.trim().toLowerCase()==="удалить"){deleteChatSession(session.id);return;}
      if(action.trim())renameChatSession(session.id,action.trim());
    });
  });
}

function renderSessionMessages(session){
  const feed=document.getElementById("chatFeed");
  feed.innerHTML="";
  const messages=session?.messages||[];
  if(!messages.length){
    appendChatMessage("assistant","Я готова. Это новый диалог. Можешь продолжать с любого вопроса или задачи.",{badge:"СИСТЕМА",system:true});
    return;
  }
  for(const message of messages){
    if(message.role!=="user"&&message.role!=="assistant")continue;
    appendChatMessage(message.role==="user"?"user":"assistant",message.content||"",{badge:message.role==="assistant"?(message.meta?.intent||"история").toUpperCase():""});
  }
}

async function loadChatSessions(openLatest=true){
  try{
    const data=await api("/api/chat/sessions");
    chatSessions=data.items||[];
    renderChatHistory();
    if(openLatest){
      const saved=localStorage.getItem("miyoriActiveChat");
      const target=chatSessions.find(x=>x.id===saved)||chatSessions[0];
      if(target)await openChatSession(target.id,false);
      else await createChatSession();
    }
  }catch(error){
    appendChatMessage("assistant","Не удалось загрузить историю диалогов: "+error.message,{badge:"ОШИБКА",system:true});
  }
}

async function openChatSession(id,closePanel=true){
  if(chatBusy)return;
  try{
    const data=await api("/api/chat/session?id="+encodeURIComponent(id));
    chatSessionId=data.session.id;
    localStorage.setItem("miyoriActiveChat",chatSessionId);
    document.getElementById("chatSessionLabel").textContent=(data.session.title||"Диалог")+" · "+(data.session.messages?.length||0)+" сообщений";
    renderSessionMessages(data.session);
    chatSessions=chatSessions.map(x=>x.id===chatSessionId?{...x,title:data.session.title,updated_at:data.session.updated_at,message_count:data.session.messages?.length||0}:x);
    renderChatHistory();
    if(closePanel)document.getElementById("chatHistoryPanel").hidden=true;
  }catch(error){
    appendChatMessage("assistant","Не удалось открыть диалог: "+error.message,{badge:"ОШИБКА",system:true});
  }
}

async function createChatSession(){
  try{
    const data=await api("/api/chat/session/create",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    chatSessionId=data.session.id;
    localStorage.setItem("miyoriActiveChat",chatSessionId);
    await loadChatSessions(false);
    await openChatSession(chatSessionId);
    prompt.focus();
  }catch(error){appendChatMessage("assistant",error.message,{badge:"ОШИБКА",system:true});}
}

async function renameChatSession(id,title){
  try{
    await api("/api/chat/session/rename",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id,title})});
    await loadChatSessions(false);
    if(id===chatSessionId)await openChatSession(id,false);
  }catch(error){appendChatMessage("assistant",error.message,{badge:"ОШИБКА",system:true});}
}

async function deleteChatSession(id){
  if(!confirm("Удалить этот диалог? Это действие нельзя отменить."))return;
  try{
    await api("/api/chat/session/delete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id})});
    if(id===chatSessionId){chatSessionId=null;localStorage.removeItem("miyoriActiveChat");}
    await loadChatSessions(true);
  }catch(error){appendChatMessage("assistant",error.message,{badge:"ОШИБКА",system:true});}
}

function appendChatMessage(role,text,options={}){
  const feed=document.getElementById("chatFeed");
  if(!feed)return null;
  const row=document.createElement("div");
  row.className="message "+(role==="user"?"user":"miyori")+(options.system?" system-message":"");
  const icon=options.icon||(role==="user"?"Я":"狐");
  const name=options.name||(role==="user"?"Вы":"Miyori Kitsune");
  const badge=options.badge?'<span>'+chatEscape(options.badge)+'</span>':'<span>'+chatTime()+'</span>';
  row.innerHTML='<div class="message-icon">'+icon+'</div><div class="message-body"><div class="message-meta"><b>'+name+'</b>'+badge+'</div><p>'+chatEscape(text).replace(/\n/g,"<br>")+'</p>'+(options.extra||"")+'</div>';
  feed.appendChild(row);
  feed.scrollTop=feed.scrollHeight;
  return row;
}

function setThinking(active,title="Miyori думает…"){
  const card=document.getElementById("thinkingCard");
  const button=document.getElementById("sendMessageButton");
  if(!card)return;
  clearInterval(thinkingTimer);
  card.hidden=!active;
  if(button)button.disabled=active;
  if(!active)return;
  document.getElementById("thinkingTitle").textContent=title;
  const steps=[
    "Собираю релевантную память и текущий контекст",
    "Miyori Brain формирует ответ и сверяет модель мира",
    "Проверяю разрешённые действия через Action Gateway",
    "Сохраняю опыт; Cloud Teacher работает отдельно, если автопроверка включена"
  ];
  let index=0;
  document.getElementById("thinkingDetail").textContent=steps[0];
  thinkingTimer=setInterval(()=>{
    index=(index+1)%steps.length;
    document.getElementById("thinkingDetail").textContent=steps[index];
  },850);
}

function renderBrainOverview(data){
  const world=data.world_model||{};
  const skills=data.skills||{};
  const learning=data.learning||{};
  const teacher=data.teacher||((data.brain||{}).teacher)||{};
  const student=data.student||((data.brain||{}).student)||{};
  const memory=data.memory_engine||{};
  const runtime=(data.brain||{}).runtime_state||{};
  document.getElementById("brainStatusVersion").textContent=student.stage==="active"?"Student v"+(student.version||"—"):"v"+((data.brain||{}).version||"—");
  const memoryEl=document.getElementById("brainMemoryStatus");
  const indexed=Number(memory.index_items||memory.vector_index?.index_items||0);
  memoryEl.textContent=indexed?indexed+" векторов":"гибридная";
  document.getElementById("brainWorldStatus").textContent=(world.nodes||0)+" объектов";
  document.getElementById("brainSkillsStatus").textContent=(skills.enabled||skills.count||0)+" активных";
  document.getElementById("brainLearningStatus").textContent=(learning.confirmed||0)+" подтверждено";
  const teacherEl=document.getElementById("brainTeacherStatus");
  teacherEl.textContent=teacher.configured?(teacher.enabled?(teacher.auto_review?"автопроверка":"готов"):"выключен"):"не настроен";
  teacherEl.classList.toggle("ok",!!(teacher.configured&&teacher.enabled));
  document.getElementById("brainRuntimeState").textContent=runtime.runtime==="cloud_ml_inference"?"MIYORI · STUDENT":(runtime.neural?"MIYORI · NEURAL":"MIYORI · PLANNER");
}

function brainOverviewText(data){
  const identity=data.identity||{},world=data.world_model||{},skills=data.skills||{},learning=data.learning||{},reflections=data.reflections||{},development=data.development||{},training=data.training||{},teacher=data.teacher||{},memory=data.memory_engine||{};
  const latest=training.latest_dataset;
  return [
    "Состояние Miyori:",
    "• стадия развития: "+(identity.development_stage||"—"),
    "• модель мира: "+(world.nodes||0)+" объектов, "+(world.edges||0)+" связей",
    "• навыки: "+(skills.enabled||skills.count||0)+" активных",
    "• обучение: "+(learning.count||0)+" наблюдений, "+(learning.confirmed||0)+" подтверждённых",
    "• рефлексии: "+(reflections.count||0),
    "• предложения развития: "+(development.active||0)+" активных",
    "• память: "+(memory.index_items||0)+" векторов в semantic index",
    "• Cloud Teacher: "+(teacher.configured?(teacher.enabled?(teacher.auto_review?"автопроверка включена":"готов"):"выключен"):"не настроен"),
    "• teacher feedback: "+(teacher.feedback_count||0),
    "• датасеты: "+(training.datasets||0)+(latest?" · последний: "+latest.records+" примеров":"")
  ].join("\n");
}

async function loadBrainOverview(showInChat=false){
  try{
    const data=await api("/api/brain/overview");
    renderBrainOverview(data);
    if(showInChat)appendChatMessage("assistant",brainOverviewText(data),{badge:"СТАТУС",system:true});
    return data;
  }catch(error){
    ["brainStatusVersion","brainMemoryStatus","brainWorldStatus","brainSkillsStatus","brainLearningStatus","brainTeacherStatus"].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent="недоступно";});
    if(showInChat)appendChatMessage("assistant","Не удалось получить внутреннее состояние: "+error.message,{badge:"ОШИБКА",system:true});
  }
}

function showTeacherFeedback(item){
  const review=item?.feedback||{};
  const corrections=Array.isArray(review.corrections)?review.corrections.filter(Boolean).slice(0,4):[];
  let text=review.summary||"Cloud Teacher завершил проверку.";
  if(corrections.length)text+="\n\nИсправления:\n• "+corrections.join("\n• ");
  const extra=item?.id?'<div class="teacher-feedback-actions"><button type="button" class="primary" data-teacher-accept>В обучение</button><button type="button" class="secondary" data-teacher-reject>Не использовать</button></div>':"";
  const row=appendChatMessage("assistant",text,{badge:"TEACHER",system:true,name:"Cloud Teacher",icon:"T",extra});
  if(!item?.id||!row)return;
  const mark=async accepted=>{
    row.querySelectorAll("button").forEach(b=>b.disabled=true);
    try{
      await api("/api/brain/teacher/feedback/mark",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:item.id,accepted_for_training:accepted})});
      row.querySelector(".teacher-feedback-actions").innerHTML='<span class="chat-action-cancelled">'+(accepted?"Принято в учебные данные":"Не используется для обучения")+'</span>';
      await loadBrainOverview(false);
    }catch(error){
      row.querySelector(".teacher-feedback-actions").innerHTML='<span class="chat-action-cancelled">'+chatEscape(error.message)+'</span>';
    }
  };
  row.querySelector("[data-teacher-accept]").addEventListener("click",()=>mark(true));
  row.querySelector("[data-teacher-reject]").addEventListener("click",()=>mark(false));
}

async function requestTeacherReview(message,studentReply,button){
  if(button){button.disabled=true;button.textContent="Teacher проверяет…";}
  try{
    const data=await api("/api/brain/teacher/review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
      message,
      student_reply:studentReply,
      session_id:chatSessionId||"default",
      project_id:activeProjectId||null
    })});
    if(button)button.textContent="Teacher проверил";
    showTeacherFeedback(data.feedback);
    await loadBrainOverview(false);
  }catch(error){
    if(button){button.disabled=false;button.textContent="Проверить Teacher";}
    appendChatMessage("assistant",error.message,{badge:"TEACHER",system:true,name:"Cloud Teacher",icon:"T"});
  }
}

function showConfirmation(result,originalMessage){
  const action=result?.plan?.actions?.[0]?.action||"действие";
  const extra='<div class="chat-confirm-actions"><button type="button" class="primary" data-brain-confirm>Подтвердить</button><button type="button" class="secondary" data-brain-cancel>Отменить</button></div>';
  const row=appendChatMessage("assistant",result.reply||"Это действие требует подтверждения.",{badge:"ПОДТВЕРЖДЕНИЕ",extra});
  pendingBrainRequest={message:originalMessage};
  row.querySelector("[data-brain-confirm]").addEventListener("click",async()=>{
    row.querySelectorAll("button").forEach(b=>b.disabled=true);
    await sendBrainMessage(originalMessage,true,false);
  });
  row.querySelector("[data-brain-cancel]").addEventListener("click",()=>{
    pendingBrainRequest=null;
    row.querySelector(".chat-confirm-actions").innerHTML='<span class="chat-action-cancelled">Отменено</span>';
  });
}

async function sendBrainMessage(value,confirmed=false,echoUser=true){
  if(chatBusy)return;
  chatBusy=true;
  if(echoUser)appendChatMessage("user",value);
  setThinking(true,confirmed?"Подтверждаю действие…":"Miyori думает…");
  try{
    const response=await fetch("/api/brain/think",{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify({
      message:value,
      session_id:chatSessionId||"default",
      project_id:activeProjectId||null,
      confirmed
    })});
    const data=await response.json().catch(()=>({}));
    if(response.status===409&&data.requires_confirmation){
      showConfirmation(data,value);
      return;
    }
    if(!response.ok||data.ok===false)throw new Error(data.error||"Ошибка Brain");
    const pipeline=data.pipeline||{};
    const trace=[
      pipeline.student_runtime?(pipeline.student_active?"мозг: Miyori Student":"мозг: "+pipeline.student_runtime):null,
      pipeline.fallback_from?"fallback: "+pipeline.fallback_from:null,
      pipeline.memory_retrieval?"память: "+pipeline.memory_retrieval:null,
      pipeline.teacher_reviewed?"Teacher: проверено":(pipeline.teacher_error?"Teacher: ошибка":null)
    ].filter(Boolean);
    const teacherReady=!!(data.brain?.teacher?.configured&&data.brain?.teacher?.enabled);
    const reviewButton=teacherReady&&!pipeline.teacher_reviewed?'<button type="button" class="teacher-review-button" data-teacher-review>Проверить Teacher</button>':"";
    const traceHtml=(trace.length||reviewButton)?'<div class="chat-trace">'+trace.map(x=>'<span>'+chatEscape(x)+'</span>').join("")+reviewButton+'</div>':"";
    const answerRow=appendChatMessage("assistant",data.reply||"Готово.",{badge:"MIYORI",extra:traceHtml});
    const teacherButton=answerRow?.querySelector("[data-teacher-review]");
    if(teacherButton)teacherButton.addEventListener("click",()=>requestTeacherReview(value,data.reply||"",teacherButton));
    if(pipeline.teacher_reviewed&&data.teacher_feedback?.id){
      const autoTrace=answerRow?.querySelector(".chat-trace");
      if(autoTrace){
        const accept=document.createElement("button");
        accept.type="button";accept.className="teacher-review-button";accept.textContent="Открыть проверку";
        accept.addEventListener("click",()=>showTeacherFeedback(data.teacher_feedback));
        autoTrace.appendChild(accept);
      }
    }
    pendingBrainRequest=null;
    await Promise.all([loadBrainOverview(false),loadWorkspace(activeProjectId),loadMemory(),refreshActiveContext()]);
    await loadChatSessions(false);
  }catch(error){
    appendChatMessage("assistant",error.message,{badge:"ОШИБКА",system:true});
  }finally{
    chatBusy=false;
    setThinking(false);
    prompt.focus();
  }
}

document.getElementById("composer").addEventListener("submit",async event=>{
  event.preventDefault();
  const value=prompt.value.trim();
  if(!value||chatBusy)return;
  prompt.value="";prompt.style.height="auto";
  if(/^\/(status|brain)$/i.test(value)||/^(как ты|какой у тебя статус|покажи статус|что у тебя сейчас|состояние системы)[?.!\s]*$/i.test(value)){
    appendChatMessage("user",value);
    setThinking(true,"Проверяю своё состояние…");
    await loadBrainOverview(true);
    setThinking(false);
    return;
  }
  await sendBrainMessage(value);
});

async function api(url,options={}){
  const response=await fetch(url,{cache:"no-store",...options});
  const data=await response.json().catch(()=>({}));
  if(!response.ok||data.ok===false)throw new Error(data.error||"Ошибка запроса");
  return data;
}

const componentLabels={core:"Ядро",interface:"Интерфейс",updater:"Обновлятор",assistant:"Miyori Action Gateway",chat:"Чат Miyori",brain:"Miyori Brain",cloudru:"Cloud.ru Training",training_data:"Данные обучения",memory:"Память",workspace:"Рабочее пространство",home:"Домашнее пространство",settings:"Настройки",account:"Личный кабинет",mobile:"Мобильное приложение"};

function applyComponentVersions(components={}){
  Object.entries(components).forEach(([name,value])=>{
    document.querySelectorAll('[data-version="'+name+'"]').forEach(el=>el.textContent="v"+value);
  });
}

function renderComponentVersions(items=[]){
  const root=document.getElementById("componentVersions");
  root.innerHTML=items.map(item=>{
    const state=item.changed?'<span class="component-change">v'+item.current+' → v'+item.latest+'</span>':'<span class="component-same">v'+item.current+'</span>';
    return '<div class="component-row"><b>'+ (componentLabels[item.name]||item.name) +'</b>'+state+'</div>';
  }).join("");
}

async function checkCore(){
  const dot=document.getElementById("healthDot"),statusText=document.getElementById("healthText"),version=document.getElementById("versionText");
  try{
    const data=await api("/api/health");
    dot.classList.add("ok");statusText.textContent="Ядро работает";version.textContent="Miyori Core v"+data.version+" · portable";
    document.getElementById("brandVersion").textContent="v"+data.version;
    document.getElementById("currentVersion").textContent="v"+data.version;
    applyComponentVersions(data.components||{});
  }catch{dot.classList.remove("ok");statusText.textContent="Ядро недоступно";version.textContent="Проверьте локальный сервер";}
}

const checkButton=document.getElementById("checkUpdateButton"),applyButton=document.getElementById("applyUpdateButton");
const latestVersion=document.getElementById("latestVersion"),updateStatus=document.getElementById("updateStatus"),updateMessage=document.getElementById("updateMessage"),updateMiniStatus=document.getElementById("updateMiniStatus"),updateDot=document.getElementById("updateDot"),updateBadge=document.getElementById("updateBadge");
let progressTimer=null;

function shortBuild(value){return value&&value!=="unknown"&&value!=="local"?String(value).slice(0,7):String(value||"—");}
function formatBytes(bytes){const n=Number(bytes||0);if(!n)return "—";const units=["Б","КБ","МБ","ГБ"];let v=n,i=0;while(v>=1024&&i<units.length-1){v/=1024;i++;}return (i? v.toFixed(v>=10?1:2):Math.round(v))+" "+units[i];}
function setUpdateNotification(count){if(count>0){updateBadge.hidden=false;updateBadge.textContent=String(count);}else{updateBadge.hidden=true;}}


async function checkUpdate(){
  checkButton.disabled=true;applyButton.disabled=true;updateStatus.textContent="Проверка…";updateMessage.textContent="Связываемся с GitHub и проверяем стабильную версию.";updateDot.classList.remove("ready");
  try{
    const data=await api("/api/update/check");
    document.getElementById("currentVersion").textContent="v"+data.current;latestVersion.textContent="v"+data.latest;renderComponentVersions(data.components||[]);
    document.getElementById("currentBuild").textContent="build "+shortBuild(data.current_build);
    document.getElementById("latestBuild").textContent="build "+shortBuild(data.latest_build);
    document.getElementById("updateSize").textContent="размер "+formatBytes(data.size);
    const issues=data.dependency_issues||[];
    const dep=document.getElementById("dependencyBox");
    if(data.dependencies_ok){dep.className="dependency-box ok";dep.textContent="Совместимость компонентов проверена: зависимости выполнены.";}
    else{dep.className="dependency-box error";dep.textContent=issues.map(x=>(componentLabels[x.component]||x.component)+" требует "+(componentLabels[x.dependency]||x.dependency)+" >= "+x.required+" (есть "+x.actual+")").join(" · ");}
    const changed=(data.components||[]).filter(x=>x.changed).length;
    setUpdateNotification(changed);
    if(data.available){updateStatus.textContent="Доступно";updateMessage.textContent=(data.changes||[]).join(" • ")||"Найдена новая версия.";updateMiniStatus.textContent="Доступно v"+data.latest;updateDot.classList.add("ready");applyButton.disabled=!data.dependencies_ok;}
    else{updateStatus.textContent="Актуально";updateMessage.textContent="Установлена последняя стабильная версия из GitHub.";updateMiniStatus.textContent="GitHub · актуально";setUpdateNotification(0);}
  }catch(error){updateStatus.textContent="Ошибка";updateMessage.textContent=error.message;updateMiniStatus.textContent="GitHub · ошибка";}
  finally{checkButton.disabled=false;}
}

async function pollProgress(){
  try{
    const data=await api("/api/update/progress");
    const box=document.getElementById("progressBox");box.hidden=false;
    document.getElementById("progressPercent").textContent=(data.progress||0)+"%";
    document.getElementById("progressBar").style.width=(data.progress||0)+"%";
    document.getElementById("progressStage").textContent=data.message||data.stage;
    document.getElementById("progressBytes").textContent=formatBytes(data.downloaded)+" / "+formatBytes(data.total);
    if(data.running)return;
    clearInterval(progressTimer);progressTimer=null;checkButton.disabled=false;
    if(data.error){updateStatus.textContent="Ошибка";updateMessage.textContent=data.error;await loadHistory();return;}
    if(data.result&&data.result.updated){updateStatus.textContent="Установлено";updateMessage.textContent="Обновление установлено. Перезапустите MiyoriKitsune.bat.";updateMiniStatus.textContent="Нужен перезапуск";setUpdateNotification(0);await loadHistory();}
  }catch(error){clearInterval(progressTimer);progressTimer=null;checkButton.disabled=false;updateMessage.textContent=error.message;}
}

async function applyUpdate(){
  if(!confirm("Установить новую версию Miyori Kitsune из GitHub? Перед обновлением будет создана резервная копия."))return;
  checkButton.disabled=true;applyButton.disabled=true;updateStatus.textContent="Установка…";updateMessage.textContent="Подготовка обновления.";
  try{await api("/api/update/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});document.getElementById("progressBox").hidden=false;progressTimer=setInterval(pollProgress,500);await pollProgress();}
  catch(error){updateStatus.textContent="Ошибка";updateMessage.textContent=error.message;checkButton.disabled=false;}
}

async function loadHistory(){
  try{
    const data=await api("/api/update/history");
    const root=document.getElementById("updateHistory");
    if(!data.items.length){root.innerHTML='<p class="empty-state">История пока пуста.</p>';return;}
    root.innerHTML=data.items.map(item=>'<div class="history-row"><div><b>v'+item.version+' · '+shortBuild(item.build)+'</b><small>'+item.date+' · '+formatBytes(item.size)+'</small></div><span class="'+(item.result==="success"?"history-ok":"history-error")+'">'+(item.result==="success"?"Успешно":"Ошибка")+'</span><p>'+((item.modules||[]).map(x=>componentLabels[x]||x).join(", ")||"Без списка модулей")+'</p></div>').join("");
  }catch{}
}

async function checkMobile(){
  const button=document.getElementById("checkMobileButton"),download=document.getElementById("downloadMobileButton");
  button.disabled=true;download.disabled=true;
  try{
    const data=await api("/api/mobile/update/check");
    document.getElementById("mobileCurrent").textContent="v"+data.current;
    document.getElementById("mobileLatest").textContent="v"+data.latest;
    document.getElementById("mobileNotes").textContent=data.notes||"Мобильный пакет опубликован.";
    document.getElementById("mobileCompatibility").textContent=data.compatible?"Совместимо с текущим Core. Требуется Core >= "+data.min_core:"Требуется обновить Core до версии "+data.min_core+" или выше.";
    download.disabled=!(data.available&&data.compatible&&data.download_ready);
  }catch(error){document.getElementById("mobileNotes").textContent=error.message;}
  finally{button.disabled=false;}
}
async function downloadMobile(){
  const button=document.getElementById("downloadMobileButton");button.disabled=true;
  try{const data=await api("/api/mobile/update/download",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});document.getElementById("mobileNotes").textContent="Пакет скачан: "+data.path;}
  catch(error){document.getElementById("mobileNotes").textContent=error.message;}
}

checkButton.addEventListener("click",checkUpdate);applyButton.addEventListener("click",applyUpdate);
document.getElementById("refreshHistoryButton").addEventListener("click",loadHistory);
document.getElementById("checkMobileButton").addEventListener("click",checkMobile);
document.getElementById("downloadMobileButton").addEventListener("click",downloadMobile);
checkCore();loadHistory();checkUpdate();checkMobile();setInterval(checkCore,15000);
const initial=location.hash.replace("#","");if(pages[initial])openPage(initial);


function profileInitials(name){
  return String(name||"AK").trim().split(/\s+/).slice(0,2).map(x=>x[0]||"").join("").toUpperCase()||"AK";
}

function renderDevices(devices=[]){
  const root=document.getElementById("deviceList");
  if(!root)return;
  if(!devices.length){root.innerHTML='<p class="empty-state">Устройств пока нет.</p>';return;}
  root.innerHTML=devices.map(device=>{
    const current=device.current?'<span class="device-current">Текущее</span>':'<button class="device-revoke" data-device-id="'+device.id+'">Отключить</button>';
    return '<div class="device-row"><span class="device-icon">'+(device.type==="mobile"?"▣":"▦")+'</span><div><b>'+device.name+'</b><small>'+device.platform+' · '+device.status+'</small></div>'+current+'</div>';
  }).join("");
  root.querySelectorAll(".device-revoke").forEach(button=>button.addEventListener("click",async()=>{
    if(!confirm("Отключить это устройство от Miyori Kitsune?"))return;
    const data=await api("/api/account/device/revoke",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:button.dataset.deviceId})});
    renderDevices(data.devices||[]);
  }));
}

function renderCloudru(cloudru={}){
  const trainingConfigured=!!(cloudru.training_configured??cloudru.configured);
  const teacherConfigured=!!cloudru.foundation_configured;
  const studentConfigured=!!cloudru.student_configured;
  document.getElementById("cloudruKeyId").value=cloudru.key_id||"";
  document.getElementById("cloudruWorkspaceId").value=cloudru.workspace_id||"";
  document.getElementById("cloudruRegion").value=cloudru.region||"SR006";
  document.getElementById("cloudruKeySecret").value="";
  document.getElementById("cloudruApiKey").value="";
  document.getElementById("cloudruFoundationApiKey").value="";
  document.getElementById("cloudruStudentApiKey").value="";
  document.getElementById("cloudruTeacherModel").value=cloudru.teacher_model||"openai/gpt-oss-120b";
  document.getElementById("cloudruStudentEndpoint").value=cloudru.student_endpoint||"";
  document.getElementById("cloudruStudentModel").value=cloudru.student_model||"Qwen/Qwen3-8B";
  document.getElementById("cloudruStudentVersion").value=cloudru.student_version||"0.1.0";
  document.getElementById("cloudruStudentEnabled").checked=!!cloudru.student_enabled;
  document.getElementById("cloudruTeacherEnabled").checked=cloudru.teacher_enabled!==false;
  document.getElementById("cloudruTeacherAutoReview").checked=!!cloudru.teacher_auto_review;
  document.getElementById("cloudruKeySecret").placeholder=cloudru.secret_saved?"Секрет сохранён — оставьте пустым, чтобы не менять":"Введите Key Secret";
  document.getElementById("cloudruApiKey").placeholder=cloudru.api_key_saved?"x-api-key сохранён — оставьте пустым, чтобы не менять":"Введите x-api-key";
  document.getElementById("cloudruFoundationApiKey").placeholder=cloudru.foundation_api_key_saved?"Foundation API Key сохранён — оставьте пустым, чтобы не менять":"Введите Foundation Models API Key";
  document.getElementById("cloudruStudentApiKey").placeholder=cloudru.student_api_key_saved?"Student API Token сохранён — оставьте пустым, чтобы не менять":"Введите ML Inference API Token";
  const state=document.getElementById("cloudruConnectionState");
  const ready=[teacherConfigured?"Teacher":null,studentConfigured?"Student":null,trainingConfigured?"GPU":null].filter(Boolean);
  state.textContent=ready.length?ready.join(" + "):"Не настроено";
  state.classList.toggle("cloudru-ready",ready.length>0);
}

function renderStudentStatus(student={}){
  const state=document.getElementById("cloudruStudentState");
  if(!state)return;
  const stage=student.stage||"unregistered";
  const score=student.evaluation_score;
  const configured=!!student.configured;
  state.textContent=configured?(stage+(score!=null?" · score "+Number(score).toFixed(2):"")):"Не настроен";
  state.classList.toggle("student-active",stage==="active");
  const evaluate=document.getElementById("evaluateCloudStudentButton");
  const activate=document.getElementById("activateCloudStudentButton");
  if(evaluate)evaluate.disabled=!configured;
  if(activate)activate.disabled=!(configured&&["testing","approved"].includes(stage)&&Number(score||0)>=0.66);
}

async function loadStudentStatus(){
  try{
    const data=await api("/api/brain/student");
    renderStudentStatus(data);
    return data;
  }catch(error){
    const state=document.getElementById("cloudruStudentState");
    if(state)state.textContent="Недоступно";
    return null;
  }
}

function renderAccount(data){
  const profile=data.profile||{};
  const name=profile.display_name||"Aspksa";
  document.getElementById("profileName").value=name;
  document.getElementById("profileLanguage").value=profile.language||"ru";
  document.getElementById("profileTheme").value=profile.theme||"dark";
  document.getElementById("profileNotifications").checked=profile.notifications!==false;
  document.getElementById("profileSync").checked=!!profile.sync_enabled;
  document.getElementById("profileLock").checked=!!profile.lock_enabled;
  document.getElementById("accountDisplayTitle").textContent=name;
  document.getElementById("accountAvatar").textContent=profileInitials(name);
  document.querySelectorAll(".profile-avatar,.top-profile").forEach(el=>el.textContent=profileInitials(name));
  document.getElementById("profileId").textContent=String(profile.profile_id||"—").slice(0,8);
  document.getElementById("syncState").textContent=profile.sync_enabled?"Включена":"Выключена";
  if(data.cloudru)renderCloudru(data.cloudru);
  loadStudentStatus();
  renderDevices(data.devices||[]);
  const pairing=data.pairing||{};
  if(pairing.active){
    document.getElementById("pairingCode").textContent=String(pairing.code).split("").join(" ");
    document.getElementById("pairingExpiry").textContent="Активен до "+new Date(pairing.expires_at*1000).toLocaleTimeString();
  }
}

async function loadAccount(){
  try{renderAccount(await api("/api/account"));}
  catch(error){document.getElementById("profileSaveStatus").textContent=error.message;}
}

document.getElementById("profileForm").addEventListener("submit",async event=>{
  event.preventDefault();
  const status=document.getElementById("profileSaveStatus");status.textContent="Сохранение…";
  try{
    const data=await api("/api/account/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
      display_name:document.getElementById("profileName").value,
      language:document.getElementById("profileLanguage").value,
      theme:document.getElementById("profileTheme").value,
      notifications:document.getElementById("profileNotifications").checked,
      sync_enabled:document.getElementById("profileSync").checked,
      lock_enabled:document.getElementById("profileLock").checked
    })});
    renderAccount({profile:data.profile,devices:(await api("/api/account")).devices});
    status.textContent="Сохранено";
  }catch(error){status.textContent=error.message;}
});

document.getElementById("cloudruForm").addEventListener("submit",async event=>{
  event.preventDefault();
  const status=document.getElementById("cloudruSaveStatus");
  status.textContent="Сохранение…";
  const payload={
    key_id:document.getElementById("cloudruKeyId").value.trim(),
    key_secret:document.getElementById("cloudruKeySecret").value,
    workspace_id:document.getElementById("cloudruWorkspaceId").value.trim(),
    api_key:document.getElementById("cloudruApiKey").value,
    region:document.getElementById("cloudruRegion").value.trim()||"SR006",
    foundation_api_key:document.getElementById("cloudruFoundationApiKey").value,
    teacher_model:document.getElementById("cloudruTeacherModel").value.trim()||"openai/gpt-oss-120b",
    teacher_enabled:document.getElementById("cloudruTeacherEnabled").checked,
    teacher_auto_review:document.getElementById("cloudruTeacherAutoReview").checked,
    student_endpoint:document.getElementById("cloudruStudentEndpoint").value.trim(),
    student_api_key:document.getElementById("cloudruStudentApiKey").value,
    student_model:document.getElementById("cloudruStudentModel").value.trim()||"Qwen/Qwen3-8B",
    student_version:document.getElementById("cloudruStudentVersion").value.trim()||"0.1.0",
    student_enabled:document.getElementById("cloudruStudentEnabled").checked
  };
  try{
    const data=await api("/api/cloudru/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    renderCloudru(data.cloudru||{});
    if(data.student)await loadStudentStatus();
    status.textContent="Сохранено локально";
  }catch(error){status.textContent=error.message;}
});

document.getElementById("testCloudStudentButton").addEventListener("click",async()=>{
  const button=document.getElementById("testCloudStudentButton");
  const status=document.getElementById("cloudruSaveStatus");
  button.disabled=true;status.textContent="Проверяю Miyori Student…";
  try{
    const data=await api("/api/cloudru/student/test",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    status.textContent="Student отвечает · "+data.latency_ms+" мс"+(data.reply?" · "+data.reply:"");
    await Promise.all([loadStudentStatus(),loadBrainOverview(false)]);
  }catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
});

document.getElementById("evaluateCloudStudentButton").addEventListener("click",async()=>{
  const button=document.getElementById("evaluateCloudStudentButton");
  const status=document.getElementById("cloudruSaveStatus");
  button.disabled=true;status.textContent="Оцениваю Student candidate…";
  try{
    const data=await api("/api/brain/student/evaluate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({project_id:activeProjectId||null})});
    status.textContent="Evaluation: "+data.report.passed+"/"+data.report.total+" · score "+Number(data.report.score||0).toFixed(2);
    await Promise.all([loadStudentStatus(),loadBrainOverview(false)]);
  }catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
});

document.getElementById("activateCloudStudentButton").addEventListener("click",async()=>{
  if(!confirm("Активировать эту версию Miyori Student как основной мозг для обычного диалога? Internal planner останется аварийным fallback."))return;
  const button=document.getElementById("activateCloudStudentButton");
  const status=document.getElementById("cloudruSaveStatus");
  button.disabled=true;status.textContent="Активирую Miyori Student…";
  try{
    const data=await api("/api/brain/student/promote",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({approved:true,min_score:0.66})});
    status.textContent="Miyori Student активирован";
    await Promise.all([loadStudentStatus(),loadBrainOverview(false)]);
  }catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
});

document.getElementById("testCloudTeacherButton").addEventListener("click",async()=>{
  const button=document.getElementById("testCloudTeacherButton");
  const status=document.getElementById("cloudruSaveStatus");
  button.disabled=true;status.textContent="Проверка Cloud Teacher…";
  try{
    const data=await api("/api/cloudru/foundation/test",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    status.textContent="Teacher подключён · "+data.latency_ms+" мс · моделей: "+(data.models_found||0);
    await Promise.all([loadAccount(),loadBrainOverview(false)]);
  }catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
});

document.getElementById("testCloudruButton").addEventListener("click",async()=>{
  const button=document.getElementById("testCloudruButton");
  const status=document.getElementById("cloudruSaveStatus");
  button.disabled=true;status.textContent="Проверка Cloud.ru…";
  try{
    const data=await api("/api/cloudru/test",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    renderCloudru(data.status||{configured:true});
    status.textContent="Подключено · "+data.latency_ms+" мс";
  }catch(error){status.textContent=error.message;}
  finally{button.disabled=false;}
});

document.getElementById("refreshDevicesButton").addEventListener("click",loadAccount);
document.getElementById("createPairingButton").addEventListener("click",async()=>{
  const button=document.getElementById("createPairingButton");button.disabled=true;
  try{
    const data=await api("/api/account/pairing",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    document.getElementById("pairingCode").textContent=String(data.code).split("").join(" ");
    document.getElementById("pairingExpiry").textContent="Активен до "+new Date(data.expires_at*1000).toLocaleTimeString();
  }catch(error){document.getElementById("pairingExpiry").textContent=error.message;}
  finally{button.disabled=false;}
});
loadAccount();

const memoryLabels={projects:"Проекты",work:"Работа",tasks:"Задачи",remember:"Запомнить",preferences:"Предпочтения",people:"Люди",facts:"Важные факты"};
let memoryState={categories:[],items:[],active_context:{count:0}};
function memEsc(v){return String(v??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch]));}
function activeMemoryCount(data){return (data.items||[]).filter(item=>(data.categories||[]).find(c=>c.id===item.category)?.enabled).length;}
function renderMemory(){
  const chips=document.getElementById("memoryChips");
  if(chips)chips.innerHTML=memoryState.categories.slice(0,4).map(c=>'<span class="'+(c.enabled?"on":"off")+'">'+memEsc(c.label)+' · '+c.count+'</span>').join("");
  const status=document.getElementById("memoryContextStatus");
  if(status)status.textContent=(memoryState.active_context?.count||0)+" записей сейчас доступны Miyori";
  const cats=document.getElementById("memoryCategoryList");
  if(cats){
    cats.innerHTML=memoryState.categories.map(c=>'<label class="memory-category-row"><span><b>'+memEsc(c.label)+'</b><small>'+c.count+' записей</small></span><input type="checkbox" data-memory-toggle="'+c.id+'" '+(c.enabled?"checked":"")+'></label>').join("");
    cats.querySelectorAll("[data-memory-toggle]").forEach(input=>input.addEventListener("change",async()=>{
      const d=await api("/api/memory/category",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({category:input.dataset.memoryToggle,enabled:input.checked})});
      memoryState={...d,active_context:{count:activeMemoryCount(d)}};renderMemory();
    }));
  }
  const items=document.getElementById("memoryItems");
  if(items){
    items.innerHTML=memoryState.items.length?memoryState.items.map(item=>'<div class="memory-item"><div><span>'+memEsc(memoryLabels[item.category]||item.category)+'</span><p>'+memEsc(item.text)+'</p></div><button type="button" data-memory-delete="'+item.id+'" title="Удалить">×</button></div>').join(""):'<p class="empty-state">Память пока пуста.</p>';
    items.querySelectorAll("[data-memory-delete]").forEach(button=>button.addEventListener("click",async()=>{
      const d=await api("/api/memory/delete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:button.dataset.memoryDelete})});
      memoryState={...d,active_context:{count:activeMemoryCount(d)}};
      renderMemory();
    }));
  }
}
async function loadMemory(){try{memoryState=await api("/api/memory");renderMemory();}catch(e){document.getElementById("memoryContextStatus").textContent=e.message;}}
function openMemory(cat){document.getElementById("memoryModal").hidden=false;if(cat)document.getElementById("memoryCategory").value=cat;document.getElementById("memoryText").focus();}
function closeMemory(){document.getElementById("memoryModal").hidden=true;}
document.getElementById("openMemoryButton").addEventListener("click",()=>openMemory());
document.getElementById("closeMemoryButton").addEventListener("click",closeMemory);
document.getElementById("memoryModal").addEventListener("click",e=>{if(e.target.id==="memoryModal")closeMemory();});
document.querySelectorAll("[data-memory-category]").forEach(b=>b.addEventListener("click",()=>openMemory(b.dataset.memoryCategory)));
document.getElementById("memoryForm").addEventListener("submit",async e=>{
  e.preventDefault();
  const t=document.getElementById("memoryText");
  if(!t.value.trim())return;
  const d=await api("/api/memory/add",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({category:document.getElementById("memoryCategory").value,text:t.value.trim(),entity_type:document.getElementById("memoryLink").value?"project":null,entity_id:document.getElementById("memoryLink").value||null})});
  t.value="";
  memoryState={...d,active_context:{count:activeMemoryCount(d)}};
  renderMemory();
  await refreshActiveContext();
});
loadMemory();


let workspaceProjects=[];
let workspaceTasks=[];
let activeProjectId=null;

function entityEscape(v){return String(v??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch]));}
function statusLabel(status){return ({active:"Активный",paused:"Пауза",completed:"Завершён",archived:"Архив",todo:"К выполнению",in_progress:"В работе",blocked:"Заблокировано",done:"Готово"}[status]||status);}
function priorityLabel(p){return ({low:"Низкий",normal:"Обычный",high:"Высокий",critical:"Критический"}[p]||p);}

function refreshProjectSelectors(){
  const options='<option value="">Без проекта</option>'+workspaceProjects.map(p=>'<option value="'+p.id+'">'+entityEscape(p.name)+'</option>').join("");
  const taskProject=document.getElementById("taskProject");if(taskProject)taskProject.innerHTML=options;
  const memoryLink=document.getElementById("memoryLink");
  if(memoryLink)memoryLink.innerHTML='<option value="">Общая память</option>'+workspaceProjects.map(p=>'<option value="'+p.id+'">Проект: '+entityEscape(p.name)+'</option>').join("");
}

function renderProjectList(){
  const root=document.getElementById("projectList");
  document.getElementById("projectCount").textContent=workspaceProjects.length;
  if(!workspaceProjects.length){root.innerHTML='<p class="empty-state">Проектов пока нет.</p>';return;}
  root.innerHTML=workspaceProjects.map(p=>'<button class="project-row '+(p.id===activeProjectId?"active":"")+'" data-project-id="'+p.id+'"><span>▦</span><div><b>'+entityEscape(p.name)+'</b><small>'+statusLabel(p.status)+'</small></div><i>›</i></button>').join("");
  root.querySelectorAll("[data-project-id]").forEach(btn=>btn.addEventListener("click",()=>selectProject(btn.dataset.projectId)));
}

function renderTaskRows(root,tasks){
  if(!tasks.length){root.innerHTML='<p class="empty-state">Задач пока нет.</p>';return;}
  root.innerHTML=tasks.map(t=>'<div class="task-row"><button class="task-check '+(t.status==="done"?"done":"")+'" data-task-toggle="'+t.id+'" title="Изменить статус">'+(t.status==="done"?"✓":"")+'</button><div><b>'+entityEscape(t.title)+'</b><small>'+priorityLabel(t.priority)+(t.project_id?" · "+entityEscape((workspaceProjects.find(p=>p.id===t.project_id)||{}).name||"Проект"):"")+'</small></div><span>'+statusLabel(t.status)+'</span></div>').join("");
  root.querySelectorAll("[data-task-toggle]").forEach(btn=>btn.addEventListener("click",async()=>{
    const task=workspaceTasks.find(t=>t.id===btn.dataset.taskToggle);if(!task)return;
    await api("/api/task/update",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:task.id,changes:{status:task.status==="done"?"todo":"done"}})});
    await loadWorkspace(activeProjectId);
  }));
}

async function selectProject(id){
  activeProjectId=id;
  renderProjectList();
  const data=await api("/api/project?id="+encodeURIComponent(id));
  document.getElementById("projectDetailEmpty").hidden=true;
  document.getElementById("projectDetail").hidden=false;
  document.getElementById("projectDetailName").textContent=data.project.name;
  document.getElementById("projectDetailDescription").textContent=data.project.description||"Описание пока не добавлено.";
  document.getElementById("projectDetailStatus").textContent=statusLabel(data.project.status);
  const summary=data.context?.summary||{};
  document.getElementById("projectContextSummary").textContent=(data.tasks?.length||0)+" задач · "+(data.context?.memory?.count||0)+" записей памяти";
  renderTaskRows(document.getElementById("projectTaskList"),data.tasks||[]);
  refreshProjectSelectors();
  document.getElementById("memoryLink").value=id;
  await refreshActiveContext();
}

async function loadWorkspace(selectId=null){
  try{
    const [projectsData,tasksData]=await Promise.all([api("/api/projects"),api("/api/tasks")]);
    workspaceProjects=projectsData.items||[];
    workspaceTasks=tasksData.items||[];
    document.getElementById("workspaceSummary").textContent=workspaceProjects.length+" проектов · "+workspaceTasks.filter(t=>t.status!=="done").length+" активных задач";
    document.getElementById("taskCount").textContent=workspaceTasks.length;
    renderProjectList();
    renderTaskRows(document.getElementById("taskList"),workspaceTasks);
    refreshProjectSelectors();
    if(selectId&&workspaceProjects.some(p=>p.id===selectId))await selectProject(selectId);
    else if(activeProjectId&&workspaceProjects.some(p=>p.id===activeProjectId))await selectProject(activeProjectId);
  }catch(error){document.getElementById("workspaceSummary").textContent=error.message;}
}

async function refreshActiveContext(){
  try{
    const url=activeProjectId?"/api/context?project_id="+encodeURIComponent(activeProjectId):"/api/context";
    const data=await api(url);
    const root=document.getElementById("activeContextChips");
    const chips=[];
    if(data.project)chips.push("Проект: "+data.project.name);
    if(data.tasks?.length)chips.push(data.tasks.filter(t=>t.status!=="done").length+" задач");
    if(data.memory?.count)chips.push(data.memory.count+" записей памяти");
    if(!chips.length)chips.push("Общий контекст");
    root.innerHTML=chips.map(x=>'<i>'+entityEscape(x)+'</i>').join("");
  }catch{}
}

function openEntityModal(id){document.getElementById(id).hidden=false;}
function closeEntityModal(id){document.getElementById(id).hidden=true;}

document.querySelectorAll("[data-close-modal]").forEach(btn=>btn.addEventListener("click",()=>closeEntityModal(btn.dataset.closeModal)));
document.getElementById("newProjectButton").addEventListener("click",()=>openEntityModal("projectModal"));
document.getElementById("newTaskButton").addEventListener("click",()=>{refreshProjectSelectors();openEntityModal("taskModal");});
document.getElementById("projectAddTaskButton").addEventListener("click",()=>{refreshProjectSelectors();document.getElementById("taskProject").value=activeProjectId||"";openEntityModal("taskModal");});
document.getElementById("refreshContextButton").addEventListener("click",refreshActiveContext);
document.getElementById("refreshBrainStatusButton").addEventListener("click",()=>loadBrainOverview(false));
document.getElementById("chatHistoryButton").addEventListener("click",()=>{
  const panel=document.getElementById("chatHistoryPanel");
  panel.hidden=!panel.hidden;
});
document.getElementById("newChatButton").addEventListener("click",createChatSession);


document.getElementById("projectForm").addEventListener("submit",async e=>{
  e.preventDefault();
  const data=await api("/api/project/create",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:document.getElementById("projectName").value,description:document.getElementById("projectDescription").value})});
  e.target.reset();closeEntityModal("projectModal");activeProjectId=data.project.id;await loadWorkspace(activeProjectId);
});

document.getElementById("taskForm").addEventListener("submit",async e=>{
  e.preventDefault();
  await api("/api/task/create",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({title:document.getElementById("taskTitle").value,project_id:document.getElementById("taskProject").value||null,priority:document.getElementById("taskPriority").value,description:document.getElementById("taskDescription").value})});
  e.target.reset();closeEntityModal("taskModal");await loadWorkspace(activeProjectId);await refreshActiveContext();
});

loadWorkspace();
refreshActiveContext();
loadBrainOverview(false);
loadChatSessions(true);
