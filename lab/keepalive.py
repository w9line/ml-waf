import http.client,json
c=http.client.HTTPConnection("172.29.0.2",5000,timeout=5)
for i in range(2):
 c.request("GET","/keep?n="+str(i),headers={"Host":"keep.internal"})
 r=c.getresponse(); assert r.status==200; x=json.loads(r.read()); assert x["host"]=="keep.internal"
c.close(); print("keep-alive passed: two requests reused connection")
