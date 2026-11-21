import argparse,os,signal
p=argparse.ArgumentParser(); p.add_argument("--file",required=True); p.add_argument("--signal",choices=["TERM","KILL","STOP"],default="TERM"); a=p.parse_args()
pid=int(open(a.file,encoding="utf-8").read().strip()); os.kill(pid,getattr(signal,"SIG"+a.signal)); print("sent",a.signal,"to",pid)
