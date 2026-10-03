const pages={chat:"Чат с Miyori Kitsune",workspace:"Рабочее пространство",home:"Домашнее пространство",settings:"Настройки",updates:"Обновление проекта",account:"Личный кабинет",mobile:"Мобильное приложение"};
const sidebar=document.getElementById("sidebar");
const title=document.getElementById("pageTitle");
const navItems=[...document.querySelectorAll(".nav-item")];

function openPage(name){
  document.querySelectorAll(".page").forEach(el=>el.classList.remove("active"));
  navItems.forEach(el=>el.classList.toggle("active",el.dataset.page===name));
  const page=document.getElementById("page-"+name);
  if(page){page.classList.add("active");title.textContent=pages[name]||"Miyori Kitsune";}
  sidebar.classList.remove("open");
}

navItems.forEach(button=>button.addEventListener("click",()=>openPage(button.dataset.page)));
document.getElementById("menuButton").addEventListener("click",()=>sidebar.classList.toggle("open"));

const prompt=document.getElementById("prompt");
prompt.addEventListener("input",()=>{prompt.style.height="auto";prompt.style.height=Math.min(prompt.scrollHeight,180)+"px";});
document.getElementById("composer").addEventListener("submit",event=>{
  event.preventDefault();
  const value=prompt.value.trim();
  if(!value)return;
  prompt.value="";
  prompt.style.height="auto";
  alert("Интерфейс чата готов. Подключение AI-модели будет следующим модулем ядра.");
});

async function checkCore(){
  const dot=document.getElementById("healthDot");
  const statusText=document.getElementById("healthText");
  const version=document.getElementById("versionText");
  try{
    const response=await fetch("/api/health",{cache:"no-store"});
    if(!response.ok)throw new Error("health");
    const data=await response.json();
    dot.classList.add("ok");
    statusText.textContent="Ядро работает";
    version.textContent="Miyori Core v"+data.version+" · portable";
  }catch{
    dot.classList.remove("ok");
    statusText.textContent="Ядро недоступно";
    version.textContent="Проверьте локальный сервер";
  }
}
checkCore();
setInterval(checkCore,15000);
