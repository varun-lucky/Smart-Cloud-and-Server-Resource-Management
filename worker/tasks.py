"""Fixed allowlisted educational tasks; no arbitrary shell execution."""
import json, os, platform, shutil, sys, time, re
from collections import Counter
def system_info():
    return {"hostname":platform.node(),"platform":platform.platform(),"python_version":sys.version.split()[0]}
def cpu_demo():
    end=time.time()+3; count=0; x=1
    while time.time()<end: x=(x*1103515245+12345)&0x7fffffff; count+=1
    return {"duration_seconds":3,"iterations":count,"checksum":x}
def disk_info():
    root="C:\\\\" if platform.system()=="Windows" else "/"; d=shutil.disk_usage(root)
    return {"root":root,"total_mb":round(d.total/1048576),"used_mb":round(d.used/1048576),"free_mb":round(d.free/1048576)}
TASKS={"system_info":system_info,"cpu_demo":cpu_demo,"disk_info":disk_info}
def text_analysis(payload):
    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str) or len(text.encode("utf-8")) > 32768:
        raise ValueError("text must be a string no larger than 32768 UTF-8 bytes")
    words = re.findall(r"\b[\w']+\b", text.lower(), flags=re.UNICODE)
    return {"word_count":len(words),"character_count":len(text),"line_count":len(text.splitlines()),
            "most_frequent_words":[{"word":w,"count":n} for w,n in Counter(words).most_common(10)]}
if __name__=="__main__":
    kind=sys.argv[1] if len(sys.argv)>1 else ""
    if kind not in TASKS and kind != "text_analysis": print(json.dumps({"error":"unsupported task"})); raise SystemExit(2)
    try:
        payload=json.loads(sys.stdin.read() or "{}")
        result=text_analysis(payload) if kind=="text_analysis" else TASKS[kind]()
        print(json.dumps(result,ensure_ascii=False))
    except Exception as e: print(json.dumps({"error":str(e)})); raise SystemExit(1)
