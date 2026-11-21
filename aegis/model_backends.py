from __future__ import annotations
import json, math, re, time
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlsplit
import numpy as np

class BaseAdapter:
    name = "base"
    thresholdable = True
    def __init__(self, path: Path): self.path = Path(path)
    def preprocess(self, sample): raise NotImplementedError
    def infer(self, prepared): raise NotImplementedError
    def predict(self, sample):
        a = time.perf_counter(); prepared = self.preprocess(sample); b = time.perf_counter(); result = self.infer(prepared); c = time.perf_counter()
        result.update(preprocess_ms=(b-a)*1000, inference_ms=(c-b)*1000, latency_ms=(c-a)*1000)
        return result

def parse_http_request(raw: str) -> dict:
    text = raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    head, sep, body = text.partition("\n\n"); lines = head.split("\n"); line = lines[0].strip() if lines else "GET / HTTP/1.1"; parts = line.split(" ", 2)
    method = parts[0].upper() if parts else "GET"; target = parts[1] if len(parts) > 1 else "/"
    if target.startswith(("http://", "https://")):
        u = urlsplit(target); target = u.path or "/"; target += ("?" + u.query) if u.query else ""
    u = urlsplit(target); headers = {}
    for item in lines[1:]:
        if ":" in item:
            k, v = item.split(":", 1); headers[k.strip()] = v.strip()
    return {"method": method, "target": target, "path": u.path or "/", "query": u.query, "headers": headers, "body": body if sep else "", "raw": text}

class ArgusAdapter(BaseAdapter):
    name = "Fizcko/argus_sentinel"
    def __init__(self, path):
        super().__init__(path)
        import onnxruntime as ort
        from tokenizers import Tokenizer
        so = ort.SessionOptions(); so.intra_op_num_threads = 1; so.inter_op_num_threads = 1; so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(self.path / "model.onnx"), sess_options=so, providers=["CPUExecutionProvider"])
        self.inputs = {x.name for x in self.session.get_inputs()}; self.outputs = [x.name for x in self.session.get_outputs()]
        self.tokenizer = Tokenizer.from_file(str(self.path / "tokenizer.json")); self.tokenizer.enable_truncation(max_length=128, direction="right"); self.tokenizer.enable_padding(length=128, direction="right", pad_id=0, pad_token="[PAD]")
        self.card_thresholds = json.loads((self.path / "thresholds.json").read_text())
    def preprocess(self, sample):
        r = parse_http_request(sample["request"]); text = f"{r['method']} {r['path']}"
        if r["query"]: text += "?" + r["query"]
        if r["body"]: text += " " + r["body"][:200]
        enc = self.tokenizer.encode(text[:500]); body = r["body"]
        numeric = np.asarray([[float(len(body)), float(len(r["headers"])), 1.0 if body else 0.0, 0.0, 0.0, 0.0]], dtype=np.float32)
        return {"input_ids": np.asarray([enc.ids], dtype=np.int32), "attention_mask": np.asarray([enc.attention_mask], dtype=np.int32), "numeric_features": numeric}
    def infer(self, p):
        out = self.session.run(None, {k:v for k,v in p.items() if k in self.inputs}); d = dict(zip(self.outputs, out)); risk = d.get("risk_score", out[-1]); probs = d.get("label_probs", out[0]); score = float(np.asarray(risk).reshape(-1)[0]); vals = np.asarray(probs).reshape(-1).tolist(); names = ["clean", "xss", "sqli", "path_traversal", "command_injection", "scanner", "spam_bot"]
        detected = [names[i] for i,x in enumerate(vals) if i and x >= self.card_thresholds.get("thresholds", {}).get(names[i], 2.0)]
        return {"score":score, "raw_label":detected[0] if detected else "clean", "label_probs":vals}

# Faithful port of the pinned AiBouncer::Classifier.request_to_text. Feature flags below
# are required upstream model preprocessing, not Aegis blocking rules.
def _bucket(x, edges, names):
    for edge, name in zip(edges, names):
        if x <= edge: return name
    return names[-1]
def _ruby_str(x):
    if isinstance(x, list): return "[" + ", ".join(_ruby_str(y) for y in x) + "]"
    return json.dumps(str(x), ensure_ascii=False)
def _ruby_hash(d): return "{" + ", ".join(_ruby_str(k) + "=>" + _ruby_str(v) for k,v in d.items()) + "}"
def aibouncer_request_to_text(r):
    method, path, body, headers = r["method"], r["path"], r["body"], r["headers"]; ua = headers.get("User-Agent", ""); params = parse_qs(r["query"], keep_blank_values=True)
    if headers.get("Content-Type", "").lower().startswith("application/x-www-form-urlencoded"):
        for k,v in parse_qs(body, keep_blank_values=True).items(): params.setdefault(k,v)
    included = {k:headers[k] for k in ("User-Agent", "Content-Type", "Accept") if k in headers}; parts = [f"METHOD:{method.upper()}", f"PATH:{path}", f"DEPTH:{path.count('/')}"]
    if params: parts.append(f"PARAMS:{len(params)}")
    if ua:
        lo = ua.lower(); scanners = ("sqlmap", "nikto", "zgrab", "nmap", "wpscan", "dirbuster", "gobuster", "nuclei", "acunetix", "burp"); bots = ("bot", "crawler", "curl", "python", "java", "wget", "go-http", "libwww", "perl", "mechanize", "axios", "node-fetch", "ruby"); browsers = ("mozilla", "chrome", "safari", "firefox", "edge", "opera")
        typ = "scanner" if any(x in lo for x in scanners) else "bot" if any(x in lo for x in bots) else "browser" if any(x in lo for x in browsers) else "unknown"; parts.append("UA_TYPE:" + typ)
    if body: parts.append("BODY_SIZE:" + ("tiny" if len(body)<=99 else "small" if len(body)<=499 else "medium" if len(body)<=1999 else "large"))
    if included:
        parts.append(f"HEADERS:{len(included)}")
        for n,v in included.items():
            if not v: continue
            low = n.lower()
            if low in ("referer", "referrer"): parts.append("HAS_REFERER")
            if low == "content-type" and "xml" in v: parts.append("HAS_XML_CONTENT")
            if low == "content-type" and "json" in v: parts.append("HAS_JSON_CONTENT")
    pv = " ".join(v for vs in params.values() for v in vs); hv = " ".join(v for v in included.values() if v); combined = f"{path} {body} {pv} {ua} {hv}"; decoded = unquote_plus(combined)
    counts = Counter(combined); entropy = -sum((n/len(combined))*math.log2(n/len(combined)) for n in counts.values()) if combined else 0.0
    parts.append("ENTROPY:" + _bucket(entropy, (2.5,4.0,5.5), ("low","normal","high","very_high")))
    depth = 0; current = combined
    for _ in range(3):
        nxt = unquote_plus(current)
        if nxt == current: break
        depth += 1; current = nxt
    if depth: parts.append(f"ENCODING:{depth}")
    special_chars = chr(39) + chr(34) + "<>(){}[];|&$`" + chr(92) + "!@#%^*=+~"; density = sum(1 for c in decoded if c in special_chars)/len(decoded) if decoded else 0.0
    parts.append("SPECIAL_DENSITY:" + _bucket(density, (0.05,0.15,0.3), ("low","normal","high","very_high")))
    q = chr(39)
    patterns = [
      (r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|OR\s+\d|AND\s+\d|--|"+re.escape(q)+r"|;|\bWHERE\b|\bFROM\b|\bSLEEP\s*\(|WAITFOR|BENCHMARK|PG_SLEEP|EXTRACTVALUE|UPDATEXML)", "FLAG:SQL_KEYWORDS"),
      (r"(<script|javascript:|onerror|onload|onmouseover|onfocus|onclick|alert\s*\(|prompt\s*\(|confirm\s*\(|<svg|<img[^>]+on\w+=|<iframe|<body[^>]+on\w+=|expression\s*\(|eval\s*\()", "FLAG:XSS_PATTERN"),
      (r"(\.\.[/\\])", "FLAG:PATH_TRAVERSAL"), (r"(\||;|`|\$\(|&&|\|\||>\s*/|<\s*/|\bcat\b|\bls\b|\bwhoami\b|\bid\b|\bping\b|\bnc\b|\bcurl\b|\bwget\b)", "FLAG:CMD_INJECTION"),
      (r"(169\.254\.169\.254|metadata\.google|127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\]|file://|gopher://|dict://|internal|\.internal)", "FLAG:SSRF_PATTERN"),
      (r"(<!DOCTYPE|<!ENTITY|SYSTEM\s*[\x22\x27]|PUBLIC\s*[\x22\x27]|%xxe|&xxe)", "FLAG:XXE_PATTERN"), (r"(\$gt|\$ne|\$lt|\$or|\$and|\$where|\$regex|\$exists|\$in|\$nin)[\x22\s:}\]]", "FLAG:NOSQL_PATTERN"),
      (r"(\{\{.*\}\}|\$\{.*\}|<%.*%>|#\{.*\}|__class__|__mro__|__subclasses__|__globals__|__builtins__|config\.|request\.|self\.)", "FLAG:SSTI_PATTERN"), (r"(\$\{jndi:|j\$\{|jn\$\{|\$\{lower:j\}|\$\{upper:j\}|ldap://|rmi://)", "FLAG:LOG4SHELL_PATTERN"),
      (r"(redirect|return|next|url|goto|dest|continue|rurl)=.*?(https?://|//)[^/]", "FLAG:REDIRECT_PATTERN"), (r"(\*\)\(|\)\(|objectClass|\)\(&\)|\)\(\|)", "FLAG:LDAP_PATTERN"),
      (r"(\.env|\.git|wp-config|phpinfo|\.aws|backup\.sql|\.htpasswd|web\.config|actuator|swagger|api-docs)", "FLAG:SCANNER_PATH"), (r"(%0d%0a|\r\n).*(Set-Cookie|Location|Content-Type|HTTP/)", "FLAG:CRLF_PATTERN"),
      (r"(Transfer-Encoding\s*:\s*(chunked|identity|xchunked)|Content-Length.*Transfer-Encoding|Transfer-Encoding.*Content-Length)", "FLAG:SMUGGLING_PATTERN"), (r"(__proto__|constructor\s*[.\[]\s*prototype)", "FLAG:PROTOTYPE_POLLUTION")]
    for pat, flag in patterns:
        if re.search(pat, decoded, re.I): parts.append(flag)
    host = headers.get("Host",headers.get("host","")); xfh = headers.get("X-Forwarded-Host",headers.get("x-forwarded-host",""))
    if re.search(r"(evil|attacker|localhost|127\.0\.0\.1|internal)",host,re.I) or re.search(r"(evil|attacker|localhost|127\.0\.0\.1|internal)",xfh,re.I): parts.append("FLAG:HOST_INJECTION")
    payload=[]
    if body: payload.append(body)
    if params: payload.append(_ruby_hash(params))
    ref = headers.get("Referer",headers.get("referer",""))
    if ref: payload.append("REFERER:"+ref)
    if payload: parts.append("PAYLOAD:"+" ".join(payload)[:500])
    return " ".join(parts)

class AiBouncerAdapter(BaseAdapter):
    name="khasinski/ai-bouncer"
    thresholdable = False
    def __init__(self,path):
        super().__init__(path)
        import onnxruntime as ort
        so=ort.SessionOptions();so.intra_op_num_threads=1;so.inter_op_num_threads=1;so.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        self.session=ort.InferenceSession(str(self.path/"embedding_model.onnx"),sess_options=so,providers=["CPUExecutionProvider"]);self.inputs=[x.name for x in self.session.get_inputs()]
        cfg=json.loads((self.path/"tokenizer_config.json").read_text());self.max_len=int(cfg.get("max_length",128));self.pad_id=int(cfg.get("pad_token_id",0));self.unk=int(cfg.get("unk_token_id",1));self.metaspace=cfg.get("metaspace_replacement","▁")
        self.vocab=json.loads((self.path/"vocab.json").read_text());self.trie={}
        for token,idx in self.vocab.items():
            node=self.trie
            for ch in token: node=node.setdefault(ch,{})
            node[None]=int(idx)
        cfg=json.loads((self.path/"config.json").read_text());self.dim=int(cfg.get("embedding_dim",256));labels=json.loads((self.path/"labels.json").read_text());self.labels=labels["labels"];self.num_vectors=int(labels["num_vectors"]);self.calibration=labels.get("calibration",{"A":-5.0,"B":2.0})
        self.vectors=np.fromfile(self.path/"vectors.bin",dtype="<f4")
        if self.vectors.size!=self.num_vectors*self.dim: raise ValueError("vectors.bin and labels.json disagree")
        self.vectors=self.vectors.reshape(self.num_vectors,self.dim);self.vectors/=np.maximum(np.linalg.norm(self.vectors,axis=1,keepdims=True),1e-8)
    def preprocess(self,sample): return {"text":aibouncer_request_to_text(parse_http_request(sample["request"]))}
    def _tokens(self,text):
        punctuation = "!" + chr(34) + "#$%&" + chr(39) + "()*+,-./:;<=>?@[" + chr(92) + "]^_" + chr(96) + "{|}~"; normalized=text.lower()
        for c in punctuation: normalized=normalized.replace(c," "+c+" ")
        text="".join(self.metaspace+w for w in re.sub(r"\s+"," ",normalized).strip().split());ids=[];pos=0
        while pos<len(text):
            node=self.trie;best=None;best_len=0;i=pos
            while i<len(text) and text[i] in node:
                node=node[text[i]];i+=1
                if None in node: best=node[None];best_len=i-pos
            if best is None: ids.append(self.unk);pos+=1
            else: ids.append(best);pos+=best_len
        if not ids: ids=[self.unk]
        ids=ids[:self.max_len];mask=[1]*len(ids)
        while len(ids)<self.max_len: ids.append(self.pad_id);mask.append(0)
        return np.asarray([ids],dtype=np.int64),np.asarray([mask],dtype=np.int64)
    def infer(self,p):
        ids,mask=self._tokens(p["text"]);out=self.session.run(None,{self.inputs[0]:ids,self.inputs[1]:mask});emb=np.asarray(out[0],dtype=np.float32).reshape(-1);emb/=max(float(np.linalg.norm(emb)),1e-8)
        sims=self.vectors@emb;idx=np.argsort(sims)[-5:][::-1];votes={}
        for i in idx: votes[self.labels[int(i)]]=votes.get(self.labels[int(i)],0.0)+float(sims[i])
        pred=max(votes,key=votes.get) if votes else "clean";total=sum(votes.values());attack=sum(v for k,v in votes.items() if k!="clean");score=attack/total if total>0 else 0.0
        nearest=float(sims[idx[0]]) if len(idx) else 0.0;vc=votes.get(pred,0.0)/total if total>0 else 0.0;raw=(nearest+vc)/2;cal=self.calibration;z=max(-60.0,min(60.0,float(cal.get("A",-5.0))*raw+float(cal.get("B",2.0))))
        return {"score":1.0 if pred != "clean" else 0.0,"raw_label":pred,"confidence":1.0/(1.0+math.exp(-z)),"nearest_similarity":nearest,"attack_vote_fraction":float(score)}

BOILERPLATE={"accept","accept-charset","accept-encoding","accept-language","cache-control","connection","content-length","dnt","keep-alive","pragma","priority","te","upgrade-insecure-requests"}
def cyberjev_normalize(raw):
    text=raw.replace("\r\n","\n")
    if not re.match(r"^[A-Z]{3,7} \S",text): return unquote_plus(text)
    head,_,body=text.partition("\n\n");first,*lines=head.split("\n");first=re.sub(r"^([A-Z]+ )https?://[^/\s]+",r"\1",first);kept=[first]
    for line in lines:
        name,sep,_=line.partition(":");low=name.strip().lower()
        if line.strip() and not (sep and (low in BOILERPLATE or low.startswith(("sec-ch-","sec-fetch-")))):kept.append(line)
    if body.strip():kept.append("body: "+body)
    return unquote_plus("\n".join(kept))
def _head_tail(tok,first,state,max_len):
    budget=max_len-len(tok(first)["input_ids"])-1;off=tok(state,add_special_tokens=False,return_offsets_mapping=True)["offset_mapping"]
    if len(off)<=budget or budget<8:return state
    head=(budget-4)//2;tail=budget-4-head
    return state[:off[head-1][1]]+" ... "+state[off[-tail][0]:]
class CyberJevAdapter(BaseAdapter):
    name="sdmlai/cyber-jev"
    def __init__(self,path):
        super().__init__(path)
        import onnxruntime as ort
        from transformers import AutoTokenizer
        so=ort.SessionOptions();so.intra_op_num_threads=1;so.inter_op_num_threads=1;so.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;so.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session=ort.InferenceSession(str(self.path/"model.int8.onnx"),sess_options=so,providers=["CPUExecutionProvider"]);self.inputs=[x.name for x in self.session.get_inputs()]
        self.tokenizer=AutoTokenizer.from_pretrained(str(self.path),local_files_only=True,use_fast=True);cfg=json.loads((self.path/"cyberjev_config.json").read_text());self.max_len=int(cfg.get("max_length",512));self.truncation=cfg.get("truncation","head")
        self.question="Is this HTTP request a web attack (SQL injection, XSS, path traversal, command injection)?";self.one=json.loads((self.path/"one_pass.model.int8.json").read_text())["http_attack"]
    def preprocess(self,sample):
        state=cyberjev_normalize(parse_http_request(sample["request"])["raw"]);option=["safe","attack"][int(self.one["option"])];first=f"question: {self.question} option: {option}"
        if self.truncation=="head_tail": state=_head_tail(self.tokenizer,first,state,self.max_len)
        enc=self.tokenizer([first],[state],truncation="only_second",max_length=self.max_len,padding="max_length",return_tensors="np")
        return {k:v for k,v in enc.items()}
    def infer(self,p):
        out=self.session.run(None,{k:v for k,v in p.items() if k in self.inputs});logit=float(np.asarray(out[0]).reshape(-1)[0]);z=(float(self.one["sign"])*logit-float(self.one["shift"]))/float(self.one["temperature"]);score=1.0/(1.0+math.exp(-max(-60.0,min(60.0,z))))
        return {"score":float(score),"raw_label":"attack" if score>=0.5 else "safe","logit":logit}

ADAPTERS={"Fizcko/argus_sentinel":ArgusAdapter,"khasinski/ai-bouncer":AiBouncerAdapter,"sdmlai/cyber-jev":CyberJevAdapter}
