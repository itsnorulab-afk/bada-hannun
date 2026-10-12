#!/usr/bin/env python3
"""Fetch KHOA daily high/low tide forecasts on CI, never expose serviceKey."""
import os, json, re, time, datetime, pathlib, urllib.request, urllib.parse
KEY=os.environ.get("KHOA_API_KEY","").strip()
URL="https://apis.data.go.kr/1192136/tideFcstHghLw/GetTideFcstHghLwApiService"
OUT=pathlib.Path("data/tides.json");OUT.parent.mkdir(exist_ok=True)
KST=datetime.timezone(datetime.timedelta(hours=9))
today=datetime.datetime.now(KST).date()
def get(code,date):
    params={"serviceKey":KEY,"type":"json","obsCode":code,"reqDate":date.strftime("%Y%m%d"),"numOfRows":"30","pageNo":"1"}
    url=URL+"?"+urllib.parse.urlencode(params,safe="%")
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"BadaHannun/2.2"}),timeout=12) as response:
        body=response.read(500000)
    return json.loads(body)
def visit(x):
    if isinstance(x,list):
        for item in x: yield from visit(item)
    elif isinstance(x,dict):
        yield x
        for value in x.values():
            if isinstance(value,(dict,list)):yield from visit(value)
def pick(x,*names):
    keys={str(k).lower():v for k,v in x.items()}
    for name in names:
        v=keys.get(name.lower())
        if v is not None and str(v).strip():return v
    return None
def parse(obj,code):
    results=[];coords=None;station=None
    for item in visit(obj):
        when=pick(item,"predcDt","predcDate","predDate","forecastDateTime","dateTime","predcTime","predcYmdHm")
        level=pick(item,"predcVal","predcLevel","tideLevel","tideHgt","predVal","tideHgt","tideHeight","predcHgt","predTide")
        extreme=pick(item,"hlCode","hLCode","highLow","extremeType","predcType","tideType","hlFlag")
        lat=pick(item,"lat","latitude","obsvLat")
        lon=pick(item,"lon","lot","longitude","obsvLon")
        name=pick(item,"obsPostName","obsName","stationName","obsPostNm")
        try:
            if lat is not None and lon is not None and 32<float(lat)<40 and 124<float(lon)<133:coords=[float(lat),float(lon)]
        except (TypeError,ValueError):pass
        if name:station=str(name)
        if when is None or level is None:continue
        dt=re.search(r"(20\d{2})[-/]?(\d{2})[-/]?(\d{2})[ T]?(\d{2}):?(\d{2})",str(when))
        if not dt:continue
        try: height=float(level)
        except (ValueError,TypeError):continue
        if not (-1000<height<2000):continue
        typ=str(extreme or "").strip().upper()
        kind="만조" if typ in ("H","HIGH","HIGH TIDE","1","고조","고") else "간조" if typ in ("L","LOW","LOW TIDE","2","저조","저") else None
        if not kind:continue
        results.append({"date":"-".join(dt.group(i) for i in (1,2,3)),"time":dt.group(4)+":"+dt.group(5),"kind":kind,"cm":round(height)})
    return coords,station,results
def main():
    if not KEY:raise RuntimeError("KHOA_API_KEY missing (only GitHub Actions secret is supported)")
    stations=[];failures=0
    # Scan official station identifiers; retain ONLY API-confirmed coordinates and readings.
    for i in range(1,61):
        code="DT_%04d"%i
        entries=[];coords=None;name=None
        for offset in range(3):
            if offset>0 and not entries:break
            day=today+datetime.timedelta(days=offset)
            try:
                pos,n,events=parse(get(code,day),code)
                if pos:coords=pos
                if n:name=n
                entries.extend(events)
            except Exception as exc:
                failures+=1
                if failures<=3:print("KHOA request failed:",type(exc).__name__)
                if offset==0:break
        if coords and entries:
            uniq={(e["date"],e["time"],e["kind"]):e for e in entries}
            stations.append({"code":code,"name":name or code,"lat":coords[0],"lon":coords[1],"events":list(uniq.values())})
        time.sleep(.05)
    result={"source":"KHOA public-data high-low tide forecast","generatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),"reference":"chart datum (official forecast)","stations":stations}
    if not stations:raise RuntimeError("No validated tide stations returned; API schema or obsCode needs verification")
    OUT.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("KHOA valid stations:",len(stations),"nonfatal requests:",failures)
if __name__=="__main__": main()
