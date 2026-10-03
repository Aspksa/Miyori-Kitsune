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
const chatSessionId="web-"+Date.now().toString(36);
let thinkingTimer=null;

function chatEscape(value){return String(value??"").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch]));}
function chatTime(){return new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});}

function appendChatMessage(role,text,options={}){
  const feed=document.getElementById("chatFeed");
  if(!feed)return null;
  const row=document.createElement("div");
  row.className="message "+(role==="user"?"user":"miyori")+(options.system?" system-message":"");
  const icon=role==="user"?"Я":"狐";
  const name=role==="user"?"Вы":"Miyori Kitsune";
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
    "Собираю память, проект и текущий контекст",
    "Сверяю модель мира и доступные навыки",
    "Формирую план и проверяю разрешённые действия",
    "Проверяю результат и сохраняю опыт"
  ];
  let index=0;
  document.getElementById("thinkingDetail").textContent=steps[0];
  thinkingTimer=setInterval(()=>{
    index=(index+1)%steps.length;
    document.getElementById("thinkingDetail").textContent=steps[index];
  },850);
}

function renderBrainOverview(data){
  const identity=data.identity||{};
  const world=data.world_model||{};
  const skills=data.skills||{};
  const learning=data.learning||{};
  const training=data.training||{};
  const cloud=training.cloudru||{};
  document.getElementById("brainStatusVersion").textContent="v"+(identity.development_stage||"—").replace("brain-","");
  document.getElementById("brainWorldStatus").textContent=(world.nodes||0)+" объектов";
  document.getElementById("brainSkillsStatus").textContent=(skills.enabled||skills.count||0)+" активных";
  document.getElementById("brainLearningStatus").textContent=(learning.confirmed||0)+" подтверждено";
  const cloudEl=document.getElementById("brainCloudStatus");
  cloudEl.textContent=cloud.configured?"подключён":"не настроен";
  cloudEl.classList.toggle("ok",!!cloud.configured);
  document.getElementById("brainRuntimeState").textContent=cloud.configured?"LOCAL + CLOUD":"LOCAL";
}

function brainOverviewText(data){
  const identity=data.identity||{},world=data.world_model||{},skills=data.skills||{},learning=data.learning||{},reflections=data.reflections||{},development=data.development||{},training=data.training||{},cloud=training.cloudru||{};
  const latest=training.latest_dataset;
  return [
    "Состояние Miyori:",
    "• стадия развития: "+(identity.development_stage||"—"),
    "• модель мира: "+(world.nodes||0)+" объектов, "+(world.edges||0)+" связей",
    "• навыки: "+(skills.enabled||skills.count||0)+" активных",
    "• обучение: "+(learning.count||0)+" наблюдений, "+(learning.confirmed||0)+" подтверждённых",
    "• рефлексии: "+(reflections.count||0),
    "• предложения развития: "+(development.active||0)+" активных",
    "• Cloud.ru: "+(cloud.configured?"настроен":"не настроен"),
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
    ["brainStatusVersion","brainWorldStatus","brainSkillsStatus","brainLearningStatus","brainCloudStatus"].forEach(id=>{const el=document.getElementById(id);if(el)el.textContent="недоступно";});
    if(showInChat)appendChatMessage("assistant","Не удалось получить внутреннее состояние: "+error.message,{badge:"ОШИБКА",system:true});
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
    const data=await api("/api/brain/think",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
      message:value,
      session_id:chatSessionId,
      project_id:activeProjectId||null,
      confirmed
    })});
    appendChatMessage("assistant",data.reply||"Готово.",{badge:(data.intent||"ответ").toUpperCase()});
    pendingBrainRequest=null;
    await Promise.all([loadBrainOverview(false),loadWorkspace(activeProjectId),loadMemory(),refreshActiveContext()]);
  }catch(error){
    try{
      const response=await fetch("/api/brain/think",{method:"POST",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:value,session_id:chatSessionId,project_id:activeProjectId||null,confirmed})});
      const data=await response.json().catch(()=>({}));
      if(response.status===409&&data.requires_confirmation)showConfirmation(data,value);
      else appendChatMessage("assistant",data.error||error.message,{badge:"ОШИБКА",system:true});
    }catch{
      appendChatMessage("assistant",error.message,{badge:"ОШИБКА",system:true});
    }
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

const componentLabels={core:"Ядро",interface:"Интерфейс",updater:"Обновлятор",assistant:"Miyori Action Gateway",chat:"Miyori Kitsune",memory:"Память",workspace:"Рабочее пространство",home:"Домашнее пространство",settings:"Настройки",account:"Личный кабинет",mobile:"Мобильное приложение"};

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
  const configured=!!cloudru.configured;
  document.getElementById("cloudruKeyId").value=cloudru.key_id||"";
  document.getElementById("cloudruWorkspaceId").value=cloudru.workspace_id||"";
  document.getElementById("cloudruRegion").value=cloudru.region||"SR006";
  document.getElementById("cloudruKeySecret").value="";
  document.getElementById("cloudruApiKey").value="";
  document.getElementById("cloudruKeySecret").placeholder=cloudru.secret_saved?"Секрет сохранён — оставьте пустым, чтобы не менять":"Введите Key Secret";
  document.getElementById("cloudruApiKey").placeholder=cloudru.api_key_saved?"x-api-key сохранён — оставьте пустым, чтобы не менять":"Введите x-api-key";
  const state=document.getElementById("cloudruConnectionState");
  state.textContent=configured?"Настроено":"Не настроено";
  state.classList.toggle("cloudru-ready",configured);
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
    region:document.getElementById("cloudruRegion").value.trim()||"SR006"
  };
  try{
    const data=await api("/api/cloudru/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    renderCloudru(data.cloudru||{});
    status.textContent="Сохранено локально";
  }catch(error){status.textContent=error.message;}
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
