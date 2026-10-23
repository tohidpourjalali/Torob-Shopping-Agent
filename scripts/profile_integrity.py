import csv,json,collections
csv.field_size_limit(10**9)
import os
P = os.getenv("DATASET_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))

# shop ids / product ids
shop_ids=set(); 
with open(f"{P}/shops.csv",encoding="utf-8",newline="") as f:
    for r in csv.DictReader(f): shop_ids.add(r["shop_id"])
prod_ids=set()
with open(f"{P}/products.csv",encoding="utf-8",newline="") as f:
    for r in csv.DictReader(f): prod_ids.add(r["product_id"])
print("shops",len(shop_ids),"products",len(prod_ids))

bad_shop=0;bad_prod=0;dup_pair=collections.Counter();pair=set();n=0
offers_per_shop=collections.Counter(); offers_per_prod=collections.Counter()
with open(f"{P}/offers.csv",encoding="utf-8",newline="") as f:
    for r in csv.DictReader(f):
        n+=1
        if r["shop_id"] not in shop_ids: bad_shop+=1
        if r["product_id"] not in prod_ids: bad_prod+=1
        k=(r["shop_id"],r["product_id"])
        if k in pair: dup_pair[k]+=1
        else: pair.add(k)
        offers_per_shop[r["shop_id"]]+=1; offers_per_prod[r["product_id"]]+=1
print("offers",n,"bad_shop_fk",bad_shop,"bad_product_fk",bad_prod,"dup(shop,product) pairs",len(dup_pair))
print("shops with offers:",len(offers_per_shop),"products with offers:",len(offers_per_prod))
print("max offers per shop:",offers_per_shop.most_common(3))

# payment channels & hours status
pc=collections.Counter(); pcat=collections.Counter(); pch=collections.Counter(); hstat=collections.Counter()
import itertools
with open(f"{P}/shops.csv",encoding="utf-8",newline="") as f:
    for r in csv.DictReader(f):
        po=r["payment_options"]
        if po and po!="null":
            for e in json.loads(po):
                pch[e.get("channel")]+=1
                for c in (e.get("category_names") or []): pcat[c]+=1
        wh=r["weekly_hours"]
        if wh and wh!="null":
            for d,v in json.loads(wh).items(): hstat[v.get("status")]+=1
print("\npayment channels:",dict(pch))
print("payment category_names top:",pcat.most_common(20))
print("hours status:",dict(hstat))

# contact channels
cc=collections.Counter()
with open(f"{P}/shops.csv",encoding="utf-8",newline="") as f:
    for r in csv.DictReader(f):
        for e in json.loads(r["contacts"]): cc[e.get("channel")]+=1
print("contact channels:",dict(cc))

# specs keys per category (sample)
cats=collections.Counter(); specsec=collections.Counter(); keysper=collections.Counter()
bad=0
with open(f"{P}/products.csv",encoding="utf-8",newline="") as f:
    for i,r in enumerate(csv.DictReader(f)):
        cats[r["category_name"]]+=1
        try:
            sp=json.loads(r["specs"]) if r["specs"] and r["specs"]!="null" else []
            keysper[len(sp)]+=1
            for e in sp: specsec[e.get("section")]+=1
        except Exception: bad+=1
        if i>120000: break
print("\ntop categories:",cats.most_common(15))
print("num categories:",len(cats))
print("specs per product (sample):",sorted(keysper.items())[:10], "... max", max(keysper) if keysper else 0)
print("spec sections:",specsec.most_common(10),"bad specs json:",bad)
