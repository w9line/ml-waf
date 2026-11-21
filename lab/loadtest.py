import argparse, concurrent.futures, json, resource, time, urllib.request
p=argparse.ArgumentParser(); p.add_argument("--url",required=True); p.add_argument("--requests",type=int,default=1000); p.add_argument("--concurrency",type=int,default=50); a=p.parse_args()
def one(i):
 t=time.perf_counter()
 try:
  req=urllib.request.Request(f"{a.url}/bench?id={i}",headers={"Host":"bench.internal"})
  with urllib.request.urlopen(req,timeout=30) as r:
   r.read()
   if r.status != 200: raise RuntimeError(str(r.status))
  return (time.perf_counter()-t)*1000,None
 except Exception as e: return (time.perf_counter()-t)*1000,str(e)
t=time.perf_counter(); results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as pool: results=list(pool.map(one,range(a.requests)))
elapsed=time.perf_counter()-t; vals=sorted(x[0] for x in results); errors=[x[1] for x in results if x[1]]
def pct(n): return round(vals[min(len(vals)-1,int((len(vals)-1)*n/100))],3)
print(json.dumps({"url":a.url,"requests":a.requests,"concurrency":a.concurrency,"success":len(vals)-len(errors),"errors":errors[:5],"rps":round(len(vals)/elapsed,2),"p50_ms":pct(50),"p95_ms":pct(95),"p99_ms":pct(99),"elapsed_s":round(elapsed,3),"client_cpu_user_s":round(resource.getrusage(resource.RUSAGE_SELF).ru_utime,3),"client_max_rss_kb":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},sort_keys=True))
if errors: raise SystemExit(1)
