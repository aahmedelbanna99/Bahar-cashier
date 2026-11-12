import sqlite3
from html import escape
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

TZ = ZoneInfo("Africa/Cairo")
MN = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
CATS = ["برفان تركيب", "مباخر", "زجاج مركات"]
SALES_COLS = ["invoice", "datetime", "item", "qty", "price", "total", "customer", "phone", "order_type", "discount", "address", "delivery_fee", "no"]
BANNER = "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"

st.set_page_config(page_title="نظام الكاشير", page_icon="🧾", layout="wide")
st.markdown(
    """<style>
.stApp,[data-testid="stDialog"]{direction:rtl}
.block-container{padding-top:3.2rem !important}
[data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.5rem}
[data-testid="stColumn"],[data-testid="column"]{min-width:28% !important;flex:1 1 28% !important}
.stButton button{width:100%;min-height:3rem}
[class*="st-key-crow"] [data-testid="stHorizontalBlock"]{flex-wrap:nowrap}
[class*="st-key-crow"] [data-testid="stColumn"],[class*="st-key-crow"] [data-testid="column"]{min-width:0 !important;flex:1 1 0 !important}
[class*="st-key-crow"] [data-testid="stColumn"]:nth-child(2),[class*="st-key-crow"] [data-testid="column"]:nth-child(2){flex:5 1 0 !important}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin:.5rem 0 1rem}
.kc{border:1px solid rgba(128,128,128,.35);border-radius:12px;padding:.7rem .9rem}
.kc small{opacity:.7;display:block}
.kc b{display:block;font-size:1.3rem;margin-top:.2rem}
</style>""",
    unsafe_allow_html=True,
)


def banner():
    st.markdown(
        f'<img src="data:image/jpeg;base64,{BANNER}" style="width:100%;border-radius:12px;margin-bottom:.6rem">',
        unsafe_allow_html=True,
    )


def sec(key, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


SHEETS = sec("gcp_service_account") is not None


# ---------------- الدخول ----------------
def login():
    if st.session_state.get("ok"):
        return
    banner()
    real = sec("APP_PASSWORD")
    if not real:
        st.error("ضيف APP_PASSWORD في Secrets بتاعة Streamlit عشان تحدد الرقم السري.")
        st.stop()
    pw = st.text_input("الرقم السري", type="password")
    if st.button("دخول"):
        if pw == real:
            st.session_state.ok = True
            st.rerun()
        else:
            st.error("الرقم السري غلط")
    st.stop()


login()


# ---------------- التخزين ----------------
# من غير إعدادات جوجل: SQLite محلي (مؤقت). بعد ما تضيف gcp_service_account في Secrets
# بيتحول لوحده لـ Google Sheets.
def conn():
    c = sqlite3.connect("cashier.db")
    c.execute("create table if not exists items(id integer primary key autoincrement, name text, price real, category text default '')")
    if "category" not in [r[1] for r in c.execute("pragma table_info(items)")]:
        c.execute("alter table items add column category text default ''")
    c.execute(
        "create table if not exists sales(id integer primary key autoincrement, invoice text, "
        "datetime text, item text, qty integer, price real, total real, customer text default '', "
        "phone text default '', order_type text default '', discount real default 0, "
        "address text default '', delivery_fee real default 0, no integer default 0)"
    )
    have = [r[1] for r in c.execute("pragma table_info(sales)")]
    for col, typ in (("customer", "text default ''"), ("phone", "text default ''"),
                     ("order_type", "text default ''"), ("discount", "real default 0"),
                     ("address", "text default ''"), ("delivery_fee", "real default 0"),
                     ("no", "integer default 0")):
        if col not in have:
            c.execute(f"alter table sales add column {col} {typ}")
    return c


if SHEETS:
    import gspread

    @st.cache_resource
    def book():
        gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        sh = gc.open_by_key(st.secrets["SHEET_ID"])
        for name, head in (("items", ["name", "price", "category"]), ("sales", SALES_COLS)):
            try:
                sh.worksheet(name)
            except gspread.WorksheetNotFound:
                sh.add_worksheet(name, rows=1000, cols=len(head)).append_row(head)
        if len(sh.worksheet("items").row_values(1)) < 3:
            sh.worksheet("items").update_cell(1, 3, "category")
        ws = sh.worksheet("sales")
        head = ws.row_values(1)
        for i, col in enumerate(SALES_COLS, start=1):
            if i > len(head):
                ws.update_cell(1, i, col)
        return sh

    @st.cache_data(ttl=30)
    def sheet_read(name):
        rows = book().worksheet(name).get_all_records(numericise_ignore=["all"] if name == "sales" else [])
        cols = ["name", "price", "category"] if name == "items" else SALES_COLS
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=cols)


def read_items():
    if SHEETS:
        df = sheet_read("items").copy()
        if "category" not in df:
            df["category"] = ""
        df["id"] = range(2, len(df) + 2)
        df["category"] = df["category"].fillna("")
        return df
    with conn() as c:
        df = pd.read_sql("select id, name, price, category from items order by id", c)
    df["category"] = df["category"].fillna("")
    return df


def add_item(name, price, category):
    if SHEETS:
        book().worksheet("items").append_row([name, float(price), category], value_input_option="RAW")
    else:
        with conn() as c:
            c.execute("insert into items(name, price, category) values(?, ?, ?)", (name, float(price), category))


def delete_item(item_id):
    if SHEETS:
        book().worksheet("items").delete_rows(int(item_id))
    else:
        with conn() as c:
            c.execute("delete from items where id=?", (int(item_id),))


def read_sales():
    if SHEETS:
        df = sheet_read("sales").copy()
        for col in SALES_COLS:
            if col not in df:
                df[col] = ""
        return df
    with conn() as c:
        return pd.read_sql(
            "select invoice, datetime, item, qty, price, total, customer, phone, order_type, discount, address, delivery_fee, no "
            "from sales order by id", c)


def add_sales(rows):
    if SHEETS:
        book().worksheet("sales").append_rows(rows, value_input_option="RAW")
    else:
        with conn() as c:
            c.executemany(
                "insert into sales(invoice, datetime, item, qty, price, total, customer, phone, order_type, discount, "
                "address, delivery_fee, no) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def delete_invoice(inv):
    if SHEETS:
        ws = book().worksheet("sales")
        rows = [i + 1 for i, v in enumerate(ws.col_values(1)) if str(v) == str(inv)]
        for rn in sorted(rows, reverse=True):
            ws.delete_rows(rn)
    else:
        with conn() as c:
            c.execute("delete from sales where invoice=?", (str(inv),))


def biz_day(now):
    # يوم العمل بيبدأ ٩ الصبح وبينتهي ٥ الفجر: أي بيع قبل ٥ الفجر بيتحسب على اليوم اللي قبله
    return (now - timedelta(hours=5)).date()


def next_no(now):
    bd = biz_day(now)
    start = f"{bd} 05:00:00"
    end = f"{bd + timedelta(days=1)} 05:00:00"
    if SHEETS:
        rows = book().worksheet("sales").get_all_records(numericise_ignore=["all"])
        sel = [r for r in rows if start <= str(r.get("datetime", "")) < end]
        nos = [int(float(r["no"])) for r in sel if str(r.get("no", "")).strip() not in ("", "0")]
        return max(max(nos, default=0), len({r["invoice"] for r in sel})) + 1
    with conn() as c:
        mx, cnt = c.execute(
            "select coalesce(max(no), 0), count(distinct invoice) from sales where datetime >= ? and datetime < ?",
            (start, end),
        ).fetchone()
    return max(mx, cnt) + 1


def category_groups(items):
    other = items[~items["category"].isin(CATS)]
    groups = [(c, items[items["category"] == c]) for c in CATS]
    if not other.empty:
        groups.append(("غير مصنف", other))
    return groups


def refresh():
    st.cache_data.clear()
    st.rerun()


# ---------------- الواجهة ----------------
banner()
if not SHEETS:
    st.caption("⚠️ التخزين مؤقت حاليًا: البيانات ممكن تتمسح لو التطبيق اتعمله إعادة تشغيل.")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_sale, tab_items, tab_rep = st.tabs(["البيع", "المنتجات", "التقارير"])

# ---------------- البيع ----------------
with tab_sale:
    items = read_items()
    cart = st.session_state.setdefault("cart", {})
    fv = st.session_state.setdefault("fv", 0)
    price = dict(zip(items["name"], items["price"]))
    groups = category_groups(items)

    if items.empty:
        st.info("مفيش منتجات لسه. روح لتاب «المنتجات» وضيف أول صنف.")
    else:
        ssel = st.session_state.get("scat")
        tiles = st.columns(len(groups))
        for col, (cat, sub) in zip(tiles, groups):
            if col.button(f"{cat} ({len(sub)})", key=f"sc_{cat}", type="primary" if ssel == cat else "secondary"):
                st.session_state.scat = None if ssel == cat else cat
                st.rerun()
        chosen = dict(groups).get(ssel)
        if chosen is not None:
            if chosen.empty:
                st.caption("لا توجد منتجات في هذا التصنيف")
            cols = st.columns(3)
            for i, r in enumerate(chosen.itertuples()):
                if cols[i % 3].button(f"{r.name}\n{r.price:g} ج", key=f"it{r.id}"):
                    cart[r.name] = cart.get(r.name, 0) + 1
                    st.rerun()

    st.markdown("<h3 style='text-align:center'>الفاتورة</h3>", unsafe_allow_html=True)
    subtotal = 0.0
    if not cart:
        st.markdown("<div style='text-align:center;opacity:.6'>لم تختر منتجات بعد</div>", unsafe_allow_html=True)
    for i, n in enumerate(list(cart)):
        q = cart[n]
        line = q * float(price.get(n, 0))
        subtotal += line
        with st.container(key=f"crow{i}"):
            cp, ct, cm = st.columns([1, 5, 1])
            if cp.button("+", key=f"p{n}"):
                cart[n] += 1
                st.rerun()
            ct.markdown(
                f"<div style='text-align:center'><b>{escape(n)}</b> × {q}<br>{line:g} ج</div>",
                unsafe_allow_html=True,
            )
            if cm.button("−", key=f"m{n}"):
                cart[n] -= 1
                if cart[n] <= 0:
                    del cart[n]
                st.rerun()

    with st.container(border=True):
        cust = st.text_input("اسم العميل", key=f"cust{fv}")
        phone = st.text_input("رقم التلفون", key=f"ph{fv}")
        otype = st.radio("نوع الطلب", ["استلام", "توصيل"], horizontal=True, key=f"ot{fv}")
        addr, fee = "", 0.0
        if otype == "توصيل":
            addr = st.text_input("العنوان", key=f"ad{fv}")
            fee = st.number_input("خدمة توصيل (سعر)", min_value=0.0, step=1.0, key=f"fe{fv}")
        st.markdown(f"**إجمالي الفاتورة:** {subtotal:g} ج")
        disc = st.number_input("خصم (مبلغ)", min_value=0.0, step=1.0, key=f"dc{fv}")
        net = subtotal - disc + fee
        st.markdown(f"### صافي الفاتورة: {max(net, 0):g} ج.م")
        if disc > subtotal:
            st.error("الخصم أكبر من إجمالي الفاتورة")

    if st.button("✅ تأكيد البيع", type="primary", disabled=(not cart or disc > subtotal)):
        now = datetime.now(TZ)
        inv = "F" + now.strftime("%y%m%d%H%M%S")
        no = next_no(now)
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for i, (n, q) in enumerate(cart.items()):
            if n in price:
                rows.append([inv, ts, n, int(q), float(price[n]), float(q * price[n]),
                             cust.strip(), phone.strip(), otype, float(disc) if i == 0 else 0.0,
                             addr.strip(), float(fee) if i == 0 else 0.0, no])
        add_sales(rows)
        st.session_state.cart = {}
        st.session_state.fv = fv + 1
        st.session_state.flash = f"تم تسجيل الفاتورة رقم {no} — الصافي {net:g} ج.م"
        refresh()
    if cart and st.button("مسح الفاتورة"):
        st.session_state.cart = {}
        st.session_state.fv = fv + 1
        st.rerun()

# ---------------- المنتجات ----------------
@st.dialog("إضافة صنف")
def add_dialog():
    n = st.text_input("المنتج")
    cat = st.selectbox("التصنيف", CATS)
    p = st.number_input("السعر", min_value=0.0, step=0.5)
    if st.button("حفظ", type="primary"):
        if not n.strip():
            st.error("اكتب اسم المنتج")
        else:
            add_item(n.strip(), p, cat)
            st.session_state.cat = cat
            refresh()


with tab_items:
    if st.button("➕ إضافة صنف", type="primary"):
        add_dialog()
    items = read_items()
    other = items[~items["category"].isin(CATS)]
    groups = [(c, items[items["category"] == c]) for c in CATS]
    if not other.empty:
        groups.append(("غير مصنف", other))
    sel = st.session_state.get("cat")
    cols = st.columns(len(groups))
    for col, (cat, sub) in zip(cols, groups):
        if col.button(f"{cat} ({len(sub)})", key=f"cat_{cat}", type="primary" if sel == cat else "secondary"):
            st.session_state.cat = None if sel == cat else cat
            st.rerun()
    chosen = dict(groups).get(sel)
    if chosen is not None:
        with st.container(border=True):
            st.subheader(sel)
            if chosen.empty:
                st.caption("لا توجد منتجات في هذا التصنيف")
            for r in chosen.itertuples():
                c1, c2 = st.columns([4, 1])
                c1.write(f"{r.name} — {r.price:g} ج")
                if c2.button("حذف", key=f"di{r.id}"):
                    delete_item(r.id)
                    refresh()

# ---------------- التقارير ----------------
def money(v):
    return f"{v:,.2f} ج"


def cards(items):
    html = "".join(f"<div class='kc'><small>{a}</small><b>{b}</b></div>" for a, b in items)
    st.markdown(f"<div class='cards'>{html}</div>", unsafe_allow_html=True)


def clean(v):
    v = "" if v is None else str(v)
    return "" if v.lower() == "nan" else v.strip()


def top_items(df):
    top = df.groupby("item")["qty"].sum().sort_values(ascending=False).head(10)
    if top.empty:
        st.write("لا مبيعات.")
    else:
        st.dataframe(top.rename_axis("الصنف").rename("الكمية"), use_container_width=True)


with tab_rep:
    s = read_sales()
    if s.empty:
        st.info("لا توجد مبيعات لسه.")
    else:
        s["dt"] = pd.to_datetime(s["datetime"])
        s["qty"] = pd.to_numeric(s["qty"], errors="coerce").fillna(0)
        s["price"] = pd.to_numeric(s["price"], errors="coerce").fillna(0)
        # الإجمالي هنا = الصافي: ناقص الخصم وزائد خدمة التوصيل (متسجلين في أول سطر من كل فاتورة)
        s["total"] = (
            pd.to_numeric(s["total"], errors="coerce").fillna(0)
            - pd.to_numeric(s["discount"], errors="coerce").fillna(0)
            + pd.to_numeric(s["delivery_fee"], errors="coerce").fillna(0)
        )
        s["day"] = (s["dt"] - pd.Timedelta(hours=5)).dt.strftime("%Y-%m-%d")
        s["month"] = s["day"].str[:7]

        today = biz_day(datetime.now(TZ))
        cur_month = today.strftime("%Y-%m")
        view = st.session_state.get("rep", "day")

        b1, b2 = st.columns(2)
        if b1.button("📅 تقارير مبيعات اليوم", type="primary" if view == "day" else "secondary", key="rb1"):
            st.session_state.rep = "day"
            st.rerun()
        if b2.button("🗓️ تقارير مبيعات الشهر", type="primary" if view == "month" else "secondary", key="rb2"):
            st.session_state.rep = "month"
            st.rerun()

        if view == "day":
            d = st.date_input("اليوم", today)
            day = d.strftime("%Y-%m-%d")
            df = s[s["day"] == day]
            st.subheader("مبيعات النهارده" if d == today else f"مبيعات يوم {day}")
            n = df["invoice"].nunique()
            tot = float(df["total"].sum())
            cards([
                ("إجمالي المبيعات", money(tot)),
                ("عدد الفواتير", str(n)),
                ("متوسط الفاتورة", money(tot / n if n else 0)),
                ("عدد القطع المباعة", f"{int(df['qty'].sum())}"),
            ])
            st.subheader("المبيعات على مدار اليوم (بالساعة)")
            hours = df.groupby(df["dt"].dt.strftime("%H"))["total"].sum()
            extra = [h for h in range(5, 9) if hours.get(f"{h:02d}", 0) > 0]
            labels = [f"{h:02d}" for h in extra + list(range(9, 24)) + list(range(0, 5))]
            hdf = pd.DataFrame({"الساعة": labels, "المبيعات": [float(hours.get(h, 0)) for h in labels]})
            st.altair_chart(
                alt.Chart(hdf).mark_bar().encode(
                    x=alt.X("الساعة:N", sort=labels, title=None), y=alt.Y("المبيعات:Q", title=None)
                ),
                use_container_width=True,
            )
            st.subheader("أكتر الأصناف مبيعًا")
            top_items(df)
            st.subheader("الفواتير")
            if df.empty:
                st.write("لا فواتير.")
            order = list(dict.fromkeys(df.sort_values("dt")["invoice"]))
            rank = {inv: i + 1 for i, inv in enumerate(order)}
            invs = []
            for inv, g in df.groupby("invoice", sort=False):
                stored = pd.to_numeric(g["no"].iloc[0], errors="coerce")
                invs.append((int(stored) if pd.notna(stored) and stored > 0 else rank[inv], inv, g))
            for no, inv, g in sorted(invs, key=lambda x: x[0]):
                f = g.iloc[0]
                sub = float((g["price"] * g["qty"]).sum())
                disc = float(pd.to_numeric(g["discount"], errors="coerce").fillna(0).sum())
                fee = float(pd.to_numeric(g["delivery_fee"], errors="coerce").fillna(0).sum())
                with st.expander(f"فاتورة رقم {no} — {f['dt']:%H:%M} — {sub - disc + fee:g} ج"):
                    for label, val in (
                        ("العميل", clean(f["customer"])),
                        ("التلفون", clean(f["phone"])),
                        ("نوع الطلب", clean(f["order_type"])),
                        ("العنوان", clean(f["address"])),
                    ):
                        if val:
                            st.markdown(f"**{label}:** {val}")
                    lines = g[["item", "qty", "price"]].copy()
                    lines["total"] = lines["qty"] * lines["price"]
                    lines.columns = ["الصنف", "الكمية", "السعر", "الإجمالي"]
                    st.dataframe(lines, hide_index=True, use_container_width=True)
                    st.markdown(f"**إجمالي الفاتورة:** {sub:g} ج")
                    if disc:
                        st.markdown(f"**الخصم:** {disc:g} ج")
                    if fee:
                        st.markdown(f"**خدمة التوصيل:** {fee:g} ج")
                    st.markdown(f"### الصافي: {sub - disc + fee:g} ج")
                    if st.button("حذف الفاتورة", key=f"ds{inv}"):
                        delete_invoice(inv)
                        refresh()
        else:
            months = sorted(set(s["month"]) | {cur_month})
            month = st.selectbox(
                "الشهر",
                months,
                index=months.index(cur_month),
                format_func=lambda m: f"{MN[int(m[5:]) - 1]} {m[:4]}",
            )
            name = f"{MN[int(month[5:]) - 1]} {month[:4]}"
            st.subheader(f"مبيعات شهر {name}" + (" (الشهر الحالي)" if month == cur_month else ""))
            df = s[s["month"] == month]
            n = df["invoice"].nunique()
            tot = float(df["total"].sum())
            per_day = df.groupby("day")["total"].sum()
            best = f"يوم {per_day.idxmax()[8:]} — {money(per_day.max())}" if not per_day.empty else "—"
            cards([
                ("إجمالي الشهر", money(tot)),
                ("عدد الفواتير", str(n)),
                ("متوسط الفاتورة", money(tot / n if n else 0)),
                ("أفضل يوم", best),
            ])
            st.subheader("مبيعات أيام الشهر")
            days = pd.date_range(f"{month}-01", periods=pd.Period(month).days_in_month)
            per_day.index = [d[8:] for d in per_day.index]
            st.bar_chart(per_day.reindex([f"{d.day:02d}" for d in days], fill_value=0))
            st.subheader("أكتر الأصناف مبيعًا في الشهر")
            top_items(df)
