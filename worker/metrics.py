import platform, shutil, psutil, os
def _disk_root():
    return "C:\\\\" if platform.system()=="Windows" else "/"
def collect_metrics():
    psutil.cpu_percent(interval=None)
    vm=psutil.virtual_memory(); d=shutil.disk_usage(_disk_root())
    return {"cpu_percent":psutil.cpu_percent(interval=None),"ram_total_mb":round(vm.total/1048576),"ram_available_mb":round(vm.available/1048576),"ram_used_percent":vm.percent,"disk_total_mb":round(d.total/1048576),"disk_free_mb":round(d.free/1048576),"disk_used_percent":round(d.used/max(d.total,1)*100,1),"platform":platform.platform(),"hostname":platform.node()}
def collect_capabilities():
    vm=psutil.virtual_memory(); d=shutil.disk_usage(_disk_root())
    return {"cpu_cores":psutil.cpu_count(logical=True) or 1,"ram_total_mb":round(vm.total/1048576),"disk_total_mb":round(d.total/1048576),"platform":platform.system(),"max_job_runtime_seconds":int(os.getenv("MAX_JOB_RUNTIME_SECONDS","30")),"max_concurrent_jobs":1}
