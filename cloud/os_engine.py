"""Phase 2 OS simulation: CPU scheduling, Banker safety, and synchronized resources."""
from collections import deque


def _validate(processes):
    if not isinstance(processes, (list, tuple)):
        raise ValueError("processes must be a list")
    seen = set()
    rows = []
    for p in processes:
        if not isinstance(p, dict):
            raise ValueError("each process must be an object")
        pid = p.get("pid")
        if isinstance(pid, bool) or not isinstance(pid, (str, int)) or str(pid).strip() == "" or pid in seen:
            raise ValueError("each process needs a unique string or integer pid")
        seen.add(pid)
        def as_integer(value, label, minimum):
            if isinstance(value, bool):
                raise ValueError(f"{label} must be an integer >= {minimum}")
            try:
                number = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"{label} must be an integer >= {minimum}")
            if str(value).strip() != str(number) or number < minimum:
                raise ValueError(f"{label} must be an integer >= {minimum}")
            return number
        arrival = as_integer(p.get("arrival", 0), "arrival", 0)
        burst = as_integer(p.get("burst", 0), "burst", 1)
        priority = as_integer(p.get("priority", 0), "priority", 0)
        rows.append(dict(p, arrival=arrival, burst=burst, priority=priority))
    return rows


def _metrics(rows, segments):
    by_pid={p["pid"]:p for p in rows}; first={}; finish={}; elapsed=0
    for pid,start,end in segments:
        if pid is not None:
            first.setdefault(pid,start); finish[pid]=end
    out=[]
    for p in rows:
        pid=p["pid"]; completion=finish[pid]; turnaround=completion-p["arrival"]
        out.append({"pid":pid,"arrival":p["arrival"],"burst":p["burst"],"priority":p["priority"],"start":first[pid],"completion":completion,"waiting":turnaround-p["burst"],"turnaround":turnaround,"response":first[pid]-p["arrival"]})
    return {"schedule":[{"pid":pid,"start":s,"end":e} for pid,s,e in segments],"processes":out,"average_waiting":round(sum(x["waiting"] for x in out)/len(out),2) if out else 0,"average_turnaround":round(sum(x["turnaround"] for x in out)/len(out),2) if out else 0,"average_response":round(sum(x["response"] for x in out)/len(out),2) if out else 0,"makespan":max((e for _,_,e in segments),default=0)}


def fcfs(processes):
    rows=sorted(_validate(processes),key=lambda p:(p["arrival"],str(p["pid"]))); t=0; seg=[]
    for p in rows:
        if t<p["arrival"]: seg.append((None,t,p["arrival"])); t=p["arrival"]
        seg.append((p["pid"],t,t+p["burst"])); t+=p["burst"]
    return _metrics(rows,seg)


def priority_nonpreemptive(processes):
    rows=_validate(processes); pending=list(rows); t=0; seg=[]
    while pending:
        ready=[p for p in pending if p["arrival"]<=t]
        if not ready:
            nxt=min(p["arrival"] for p in pending); seg.append((None,t,nxt)); t=nxt; continue
        p=min(ready,key=lambda x:(x["priority"],x["arrival"],str(x["pid"])))
        seg.append((p["pid"],t,t+p["burst"])); t+=p["burst"]; pending.remove(p)
    return _metrics(rows,seg)


def round_robin(processes, quantum):
    if isinstance(quantum, bool):
        raise ValueError("quantum must be a positive integer")
    try:
        qsize = int(quantum)
    except (TypeError, ValueError):
        raise ValueError("quantum must be a positive integer")
    if str(quantum).strip() != str(qsize) or qsize <= 0:
        raise ValueError("quantum must be a positive integer")
    rows=_validate(processes); arrivals=sorted(rows,key=lambda p:(p["arrival"],str(p["pid"])))
    remaining={p["pid"]:p["burst"] for p in rows}; t=0; i=0; q=deque(); seg=[]
    while i<len(arrivals) or q:
        if not q and i<len(arrivals) and t<arrivals[i]["arrival"]:
            seg.append((None,t,arrivals[i]["arrival"])); t=arrivals[i]["arrival"]
        while i<len(arrivals) and arrivals[i]["arrival"]<=t: q.append(arrivals[i]); i+=1
        p=q.popleft(); run=min(qsize,remaining[p["pid"]]); seg.append((p["pid"],t,t+run)); t+=run; remaining[p["pid"]]-=run
        while i<len(arrivals) and arrivals[i]["arrival"]<=t: q.append(arrivals[i]); i+=1
        if remaining[p["pid"]]>0: q.append(p)
    return _metrics(rows,seg)


def bankers_safety(available, allocation, maximum):
    """Return Banker's safe-state result; matrices are process -> resource vectors."""
    if not isinstance(available, (list, tuple)) or not isinstance(allocation, (list, tuple)) or not isinstance(maximum, (list, tuple)):
        raise ValueError("available, allocation and maximum must be lists")
    if len(allocation) != len(maximum):
        raise ValueError("allocation and maximum process counts differ")
    if any(not isinstance(row, (list, tuple)) for row in list(allocation) + list(maximum)):
        raise ValueError("allocation and maximum must contain resource vectors")
    def vector(values, label):
        result = []
        for value in values:
            if isinstance(value, bool):
                raise ValueError(f"{label} values must be non-negative integers")
            try:
                number = int(value)
            except (TypeError, ValueError):
                raise ValueError(f"{label} values must be non-negative integers")
            if str(value).strip() != str(number) or number < 0:
                raise ValueError(f"{label} values must be non-negative integers")
            result.append(number)
        return result
    available = vector(available, "available")
    allocation = [vector(row, "allocation") for row in allocation]
    maximum = [vector(row, "maximum") for row in maximum]
    n, m = len(allocation), len(available)
    if any(len(row) != m for row in allocation + maximum):
        raise ValueError("resource vector width mismatch")
    need = [[maximum[i][j] - allocation[i][j] for j in range(m)] for i in range(n)]
    if any(value < 0 for row in need for value in row):
        raise ValueError("allocation cannot exceed maximum claim")
    work = list(available)
    finish = [False] * n
    sequence = []
    while len(sequence) < n:
        found = False
        for i in range(n):
            if not finish[i] and all(need[i][j] <= work[j] for j in range(m)):
                work = [work[j] + allocation[i][j] for j in range(m)]
                finish[i] = True
                sequence.append(i)
                found = True
        if not found:
            break
    return {"safe": all(finish), "safe_sequence": sequence if all(finish) else [], "need": need, "unfinished_processes": [i for i, done in enumerate(finish) if not done]}

