import json,sys
mode=sys.argv[1]; x=json.loads(sys.argv[2])
if mode=="get": assert x["method"]=="GET" and x["host"]=="proof.internal" and x["path"]=="/path" and x["query"]=="a=1&b=two" and x["service"]=="flask"
elif mode=="post": assert x["method"]=="POST" and x["body"]=="{\"v\":42}"
elif mode=="fastapi": assert x["service"]=="fastapi" and x["host"]=="api.internal" and x["query"]=="y=1"
elif mode=="nginx": assert x["host"]=="nginx.internal" and x["path"]=="/nginx"
print(mode+": verified")
