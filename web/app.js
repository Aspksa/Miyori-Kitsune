const pages={chat:"Чат с Miyori Kitsune",workspace:"Рабочее пространство",home:"Домашнее пространство",settings:"Настройки",updates:"Обновление проекта",account:"Личный кабинет",mobile:"Мобильное приложение"};
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
document.getElementById("composer").addEventListener("submit",event=>{event.preventDefault();if(!prompt.value.trim())return;prompt.value="";prompt.style.height="auto";alert("Оболочка чата готова. Следующий этап — подключение AI-модели и памяти.");});

async function api(url,options={}){
  const response=await fetch(url,{cache:"no-store",...options});
  const data=await response.json().catch(()=>({}));
  if(!response.ok||data.ok===false)throw new Error(data.error||"Ошибка запроса");
  return data;
}

async function checkCore(){
  const dot=document.getElementById("healthDot"),statusText=document.getElementById("healthText"),version=document.getElementById("versionText");
  try{
    const data=await api("/api/health");
    dot.classList.add("ok");statusText.textContent="Ядро работает";version.textContent="Miyori Core v"+data.version+" · portable";
    document.getElementById("brandVersion").textContent="v"+data.version;
    document.getElementById("currentVersion").textContent="v"+data.version;
  }catch{dot.classList.remove("ok");statusText.textContent="Ядро недоступно";version.textContent="Проверьте локальный сервер";}
}

const checkButton=document.getElementById("checkUpdateButton"),applyButton=document.getElementById("applyUpdateButton");
const latestVersion=document.getElementById("latestVersion"),updateStatus=document.getElementById("updateStatus"),updateMessage=document.getElementById("updateMessage"),updateMiniStatus=document.getElementById("updateMiniStatus"),updateDot=document.getElementById("updateDot");

async function checkUpdate(){
  checkButton.disabled=true;applyButton.disabled=true;updateStatus.textContent="Проверка…";updateMessage.textContent="Связываемся с GitHub и проверяем стабильную версию.";updateDot.classList.remove("ready");
  try{
    const data=await api("/api/update/check");
    document.getElementById("currentVersion").textContent="v"+data.current;latestVersion.textContent="v"+data.latest;
    if(data.available){updateStatus.textContent="Доступно";updateMessage.textContent="Найдена новая версия. Перед установкой будет создана резервная копия.";updateMiniStatus.textContent="Доступно v"+data.latest;updateDot.classList.add("ready");applyButton.disabled=false;}
    else{updateStatus.textContent="Актуально";updateMessage.textContent="Установлена последняя стабильная версия из GitHub.";updateMiniStatus.textContent="GitHub · актуально";}
  }catch(error){updateStatus.textContent="Ошибка";updateMessage.textContent=error.message;updateMiniStatus.textContent="GitHub · ошибка";}
  finally{checkButton.disabled=false;}
}

async function applyUpdate(){
  if(!confirm("Установить новую версию Miyori Kitsune из GitHub? Перед обновлением будет создана резервная копия."))return;
  checkButton.disabled=true;applyButton.disabled=true;updateStatus.textContent="Установка…";updateMessage.textContent="Скачивание и замена файлов. Не закрывайте окно ядра.";
  try{
    const data=await api("/api/update/apply",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    if(data.updated){latestVersion.textContent="v"+data.latest;updateStatus.textContent="Установлено";updateMessage.textContent="Обновление установлено. Закройте окно ядра и снова запустите MiyoriKitsune.bat.";updateMiniStatus.textContent="Нужен перезапуск";updateDot.classList.add("ready");}
    else{updateStatus.textContent="Актуально";updateMessage.textContent="Обновление не требуется.";checkButton.disabled=false;}
  }catch(error){updateStatus.textContent="Ошибка";updateMessage.textContent=error.message;checkButton.disabled=false;}
}
checkButton.addEventListener("click",checkUpdate);applyButton.addEventListener("click",applyUpdate);
checkCore();setInterval(checkCore,15000);
const initial=location.hash.replace("#","");if(pages[initial])openPage(initial);
