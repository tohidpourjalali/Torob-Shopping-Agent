import csv, json, sys, collections
csv.field_size_limit(10**9)
import os
P = os.getenv("DATASET_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))

def prof(name, n=None, jsoncols=(), listcols=()):
    path=f"{P}/{name}.csv"
    rows=0; none=collections.Counter(); vals=collections.Counter()
    jkeys=collections.defaultdict(collections.Counter); badjson=collections.Counter()
    llen=collections.Counter(); lkeys=collections.defaultdict(collections.Counter)
    ids=set(); dup=0
    with open(path, encoding="utf-8", newline="") as f:
        r=csv.DictReader(f)
        cols=r.fieldnames
        idcol=[c for c in cols if c.endswith("_id") and c in ("shop_id","product_id","offer_id")]
        idcol=idcol[0] if idcol else None
        for i,row in enumerate(r):
            rows+=1
            for c in cols:
                v=row[c]
                if v is None or v=="" or v=="null": none[c]+=1
            if idcol:
                v=row[idcol]
                if v in ids: dup+=1
                else: ids.add(v)
            for c in jsoncols:
                v=row.get(c)
                if v and v!="null":
                    try:
                        o=json.loads(v)
                        if isinstance(o,dict):
                            for k in o: jkeys[c][k]+=1
                        elif isinstance(o,list):
                            llen[f"{c}.len={len(o)}"]+=1
                            for e in o:
                                if isinstance(e,dict):
                                    for k in e: lkeys[c][k]+=1
                    except Exception as e:
                        badjson[c]+=1
            if n and rows>=n: break
    print(f"\n=== {name}.csv  rows={rows:,}  cols={cols}")
    print("  duplicate ids:", dup)
    print("  null/empty counts:", {k:v for k,v in none.items() if v})
    if jkeys:
        print("  dict json keys:", {k:dict(v.most_common(25)) for k,v in jkeys.items()})
    if lkeys:
        print("  list elem keys:", {k:dict(v.most_common(25)) for k,v in lkeys.items()})
    if llen: print("  list lengths:", dict(llen.most_common(8)))
    if badjson: print("  BAD JSON:", dict(badjson))

prof("shops", jsoncols=("payment_options","weekly_hours","contacts"))
prof("products", jsoncols=("image_urls",))
prof("offers")
