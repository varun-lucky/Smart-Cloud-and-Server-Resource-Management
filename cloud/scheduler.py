def choose_worker(workers, cpu_cores, ram_mb, disk_mb):
    """Baseline placement: eligible workers only, then lowest-load/least-waste score."""
    candidates = []
    for w in workers:
        if not w.get("online"): continue
        m, c = w.get("metrics") or {}, w.get("capabilities") or {}
        cpu_total = int(c.get("cpu_cores", 0) or 0)
        ram_total = int(c.get("ram_total_mb", 0) or 0)
        disk_total = int(c.get("disk_total_mb", 0) or 0)
        if cpu_total < cpu_cores or ram_total < ram_mb or disk_total < disk_mb: continue
        if int(m.get("ram_available_mb", 0) or 0) < ram_mb: continue
        if int(m.get("disk_free_mb", 0) or 0) < disk_mb: continue
        load = float(m.get("cpu_percent", 100) or 0)
        score = load + (ram_mb / max(ram_total, 1))*100 + (disk_mb / max(disk_total, 1))*10
        candidates.append((score, w))
    return min(candidates, key=lambda x: x[0])[1] if candidates else None
