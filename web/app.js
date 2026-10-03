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
document.getElementById("composer").addEventListener("submit",event=>{event.preventDefault();if(!prompt.value.trim())return;prompt.value="";prompt.style.height="auto";alert("Miyori готова как интерфейс личной помощницы. Следующий этап — подключение AI-модели, памяти и инструментов.");});

async function api(url,options={}){
  const response=await fetch(url,{cache:"no-store",...options});
  const data=await response.json().catch(()=>({}));
  if(!response.ok||data.ok===false)throw new Error(data.error||"Ошибка запроса");
  return data;
}

const componentLabels={core:"Ядро",interface:"Интерфейс",updater:"Обновлятор",chat:"Чат",workspace:"Рабочее пространство",home:"Домашнее пространство",settings:"Настройки",account:"Личный кабинет",mobile:"Мобильное приложение"};

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
  if(items)items.innerHTML=memoryState.items.length?memoryState.items.map(item=>'<div class="memory-item"><div><span>'+memEsc(memoryLabels[item.category]||item.category)+'</span><p>'+memEsc(item.text)+'</p></div></div>').join(""):'<p class="empty-state">Память пока пуста.</p>';
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
  const d=await api("/api/memory/add",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({category:document.getElementById("memoryCategory").value,text:t.value.trim()})});
  t.value="";
  memoryState={...d,active_context:{count:activeMemoryCount(d)}};
  renderMemory();
});
loadMemory();
