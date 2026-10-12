#!/usr/bin/env python3
"""Build public KHOA tide forecasts on GitHub Actions, without exposing API keys."""
import os,json,datetime,pathlib,urllib.parse,urllib.request,concurrent.futures,time,random
BASE="https://apis.data.go.kr/1192136/tideFcstHghLw/GetTideFcstHghLwApiService"
key=urllib.parse.unquote(os.environ.get("KHOA_API_KEY","").strip())
out=pathlib.Path("data/tides.json")
kst=datetime.timezone(datetime.timedelta(hours=9))
today=datetime.datetime.now(kst).date()
stations=json.loads(pathlib.Path("data/khoa-stations.json").read_text(encoding="utf8"))["stations"]
def get(code,day):
    params={"serviceKey":key,"obsCode":code,"reqDate":day.strftime("%Y%m%d"),"numOfRows":"300","type":"json"}
    url=BASE+"?"+urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"BadaHannun/2.2"}),timeout=18) as r:
        data=r.read(1000000)
    obj=json.loads(data)
    if obj.get("response",{}).get("header",{}).get("resultCode") not in (None,"00","0","0000"):
        raise ValueError("API response resultCode not successful")
    if not isinstance(obj.get("body"),dict):
        raise ValueError("Unexpected API envelope; expected body.items.item")
    return obj
def parse(obj):
    raw=(obj.get("body",{}).get("items") or {}).get("item") or []
    if isinstance(raw,dict):raw=[raw]
    out=[]
    for it in raw:
        if not isinstance(it,dict):continue
        dt=str(it.get("predcDt","")).strip()
        if len(dt)<16:continue
        dt=dt.replace("T"," ")
        date=dt[:10];hm=dt[11:16]
        try:datetime.date.fromisoformat(date)
        except ValueError:continue
        if len(hm)!=5 or hm[2]!=":":continue
        try:cm=round(float(it["predcTdlvVl"]))
        except (KeyError,ValueError,TypeError):continue
        typ=str(it.get("extrSe","")).strip()
        kind="만조" if typ in ("1","3") else "간조" if typ in ("2","4") else None
        if kind and -500<=cm<=1800:out.append({"date":date,"time":hm,"kind":kind,"cm":cm})
    return out
def read_station(st):
    events=[]
    for i in range(3):
        day=today+datetime.timedelta(days=i)
        try:events+=parse(get(st["code"],day))
        except Exception as ex:
            if not events: return None
            break
    unique={(e["date"],e["time"],e["kind"]):e for e in events}
    return dict(st,events=sorted(unique.values(),key=lambda x:(x["date"],x["time"]))) if unique else None
def main():
    if not key:raise RuntimeError("Missing Actions secret KHOA_API_KEY")
    first=get("DT_0001",today)
    sample=parse(first)
    if not sample:
        keys=list(((first.get("body",{}).get("items") or {}).get("item") or [{}]))
        raise RuntimeError("API returned no valid tide extrema; check API response mapping predcDt/predcTdlvVl/extrSe")
    print("KHOA first station returned",len(sample),"validated tides; loading",len(stations),"registered stations")
    collected=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for result in pool.map(read_station,stations):
            if result:collected.append(result)
    if not collected:raise RuntimeError("No valid stations; previous tide file preserved if any")
    out.parent.mkdir(exist_ok=True)
    payload={"source":"KHOA high-low tide forecast","generatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),"reference":"Official chart datum values (cm)","stations":collected}
    out.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf8")
    print("Tide stations with valid readings:",len(collected),"/",len(stations))
if __name__=="__main__":main()
