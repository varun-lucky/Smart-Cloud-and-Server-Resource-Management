import os,time,uuid,json,subprocess,sys,socket,requests
from dotenv import load_dotenv
from worker.metrics import collect_metrics,collect_capabilities
load_dotenv(
    os.path.join(
        os.path.dirname(__file__),
        os.getenv("WORKER_ENV_FILE", ".env")
    )
)
BASE=os.getenv("CONTROLLER_URL","http://127.0.0.1:5000").rstrip("/")
TOKEN=os.getenv("WORKER_SHARED_TOKEN","CHANGE_ME")
NAME=os.getenv("WORKER_NAME",socket.gethostname())
WID=os.getenv("WORKER_ID") or str(uuid.uuid4())
INTERVAL=int(os.getenv("HEARTBEAT_INTERVAL_SECONDS","10"))
TIMEOUT=int(os.getenv("HTTP_TIMEOUT_SECONDS","10"))
if TOKEN=="CHANGE_ME": raise SystemExit("Set WORKER_SHARED_TOKEN in worker .env.")
S=requests.Session(); S.headers.update({"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json"})
def post(path,data):
    r=S.post(BASE+path,json=data,timeout=TIMEOUT); r.raise_for_status(); return r.json()
def run_job(j):
    jid=j["job_id"]; kind=j["job_type"]
    if kind not in ("system_info","cpu_demo","disk_info","text_analysis"):
        post("/api/worker/job-result",{"job_id":jid,"worker_id":WID,"status":"FAILED","error":"unsupported task"}); return
    p=None
    try:
        p=subprocess.Popen([sys.executable,"-m","worker.tasks",kind],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,cwd=os.path.abspath(os.path.join(os.path.dirname(__file__),"..")))
        post("/api/worker/job-result",{"job_id":jid,"worker_id":WID,"status":"RUNNING","os_pid":p.pid})
        try: out,err=p.communicate(input=json.dumps(j.get("input") or {}),timeout=int(os.getenv("MAX_JOB_RUNTIME_SECONDS","120")))
        except subprocess.TimeoutExpired:
            p.kill(); p.communicate(); raise TimeoutError("job exceeded runtime limit")
        if p.returncode: raise RuntimeError((err or out or "task failed")[:1000])
        result=json.loads(out.strip().splitlines()[-1])
        post("/api/worker/job-result",{"job_id":jid,"worker_id":WID,"status":"COMPLETED","os_pid":p.pid,"result":result})
        print(f"{jid} completed; OS PID={p.pid}")
    except Exception as e:
        try: post("/api/worker/job-result",{"job_id":jid,"worker_id":WID,"status":"FAILED","os_pid":p.pid if p else None,"error":str(e)[:1000]})
        except Exception: pass
        print(f"{jid} failed: {e}")
def main():
    post("/api/worker/register",{"worker_id":WID,"name":NAME,"capabilities":collect_capabilities(),"metrics":collect_metrics()})
    print(f"Registered {NAME} ({WID}) -> {BASE}")
    while True:
        try:
            post("/api/worker/heartbeat",{"worker_id":WID,"capabilities":collect_capabilities(),"metrics":collect_metrics()})
            j=post("/api/worker/next-job",{"worker_id":WID}).get("job")
            if j: run_job(j)
        except requests.RequestException as e: print("Controller connection error:",e)
        except Exception as e: print("Agent error:",e)
        time.sleep(max(3,INTERVAL))
if __name__=="__main__": main()
