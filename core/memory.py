from __future__ import annotations
import json, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
MEMORY_FILE=ROOT/"data"/"memory.json"
CATEGORIES={"projects":"Проекты","work":"Работа","tasks":"Задачи","remember":"Запомнить","preferences":"Предпочтения","people":"Люди","facts":"Важные факты"}
def _default(): return {"enabled":{k:True for k in CATEGORIES},"items":[]}
def _read():
    try:
        data=json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data,dict): return _default()
    except (OSError,json.JSONDecodeError): return _default()
    enabled=_default()["enabled"]; enabled.update({k:bool(v) for k,v in data.get("enabled",{}).items() if k in CATEGORIES})
    items=[x for x in data.get("items",[]) if isinstance(x,dict) and x.get("category") in CATEGORIES]
    return {"enabled":enabled,"items":items}
def _write(data):
    MEMORY_FILE.parent.mkdir(parents=True,exist_ok=True); tmp=MEMORY_FILE.with_suffix(".json.tmp"); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(MEMORY_FILE)
def get_memory():
    s=_read(); return {"categories":[{"id":k,"label":v,"enabled":s["enabled"].get(k,True),"count":sum(1 for x in s["items"] if x.get("category")==k)} for k,v in CATEGORIES.items()],"items":sorted(s["items"],key=lambda x:int(x.get("updated_at",0)),reverse=True)}
def add_memory(category,text):
    if category not in CATEGORIES: raise ValueError("Неизвестная категория памяти.")
    text=str(text).strip()
    if not text: raise ValueError("Запись памяти пустая.")
    if len(text)>2000: raise ValueError("Запись памяти слишком длинная.")
    s=_read(); now=int(time.time()); item={"id":uuid.uuid4().hex[:12],"category":category,"text":text,"created_at":now,"updated_at":now}; s["items"].append(item); _write(s); return item
def delete_memory(item_id):
    s=_read(); n=len(s["items"]); s["items"]=[x for x in s["items"] if x.get("id")!=item_id]; changed=len(s["items"])!=n
    if changed: _write(s)
    return changed
def set_category_enabled(category,enabled):
    if category not in CATEGORIES: raise ValueError("Неизвестная категория памяти.")
    s=_read(); s["enabled"][category]=bool(enabled); _write(s); return {"category":category,"enabled":s["enabled"][category]}
def active_context():
    s=_read(); items=[x for x in s["items"] if s["enabled"].get(x.get("category"),False)]; return {"enabled_categories":[k for k,v in s["enabled"].items() if v],"items":items,"count":len(items)}
