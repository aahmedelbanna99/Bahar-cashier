import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

TZ = ZoneInfo("Africa/Cairo")
MN = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
CATS = ["برفان تركيب", "مباخر", "زجاج مركات"]
SALES_COLS = ["invoice", "datetime", "item", "qty", "price", "total"]

st.set_page_config(page_title="نظام الكاشير", page_icon="🧾", layout="wide")
st.markdown(
    """<style>
.stApp,[data-testid="stDialog"]{direction:rtl}
[data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.5rem}
[data-testid="stColumn"],[data-testid="column"]{min-width:28% !important;flex:1 1 28% !important}
.stButton button{width:100%;min-height:3rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;margin:.5rem 0 1rem}
.kc{border:1px solid rgba(128,128,128,.35);border-radius:12px;padding:.7rem .9rem}
.kc small{opacity:.7;display:block}
.kc b{display:block;font-size:1.3rem;margin-top:.2rem}
</style>""",
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
    st.title("🧾 نظام الكاشير")
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
        "datetime text, item text, qty integer, price real, total real)"
    )
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
        return sh

    @st.cache_data(ttl=30)
    def sheet_read(name):
        rows = book().worksheet(name).get_all_records()
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
        return sheet_read("sales").copy()
    with conn() as c:
        return pd.read_sql("select invoice, datetime, item, qty, price, total from sales order by id", c)


def add_sales(rows):
    if SHEETS:
        book().worksheet("sales").append_rows(rows, value_input_option="RAW")
    else:
        with conn() as c:
            c.executemany("insert into sales(invoice, datetime, item, qty, price, total) values(?,?,?,?,?,?)", rows)


def delete_invoice(inv):
    if SHEETS:
        ws = book().worksheet("sales")
        rows = [i + 1 for i, v in enumerate(ws.col_values(1)) if str(v) == str(inv)]
        for rn in sorted(rows, reverse=True):
            ws.delete_rows(rn)
    else:
        with conn() as c:
            c.execute("delete from sales where invoice=?", (str(inv),))


def refresh():
    st.cache_data.clear()
    st.rerun()


# ---------------- الواجهة ----------------
if not SHEETS:
    st.caption("⚠️ التخزين مؤقت حاليًا: البيانات ممكن تتمسح لو التطبيق اتعمله إعادة تشغيل.")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

tab_sale, tab_items, tab_rep = st.tabs(["البيع", "المنتجات", "التقارير"])

# ---------------- البيع ----------------
with tab_sale:
    items = read_items()
    cart = st.session_state.setdefault("cart", {})
    if items.empty:
        st.info("مفيش أصناف لسه. روح لتاب «الأصناف» وضيف أول صنف.")
    else:
        cols = st.columns(3)
        for i, r in items.reset_index(drop=True).iterrows():
            if cols[i % 3].button(f"{r['name']}\n{r['price']:g} ج", key=f"it{i}"):
                cart[r["name"]] = cart.get(r["name"], 0) + 1
    price = dict(zip(items["name"], items["price"]))
    if cart:
        st.subheader("الفاتورة الحالية")
        total = 0.0
        for n in list(cart):
            q = cart[n]
            line = q * float(price.get(n, 0))
            total += line
            c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
            c1.write(f"{n} — {line:g} ج")
            if c2.button("−", key=f"m{n}"):
                cart[n] -= 1
                if cart[n] <= 0:
                    del cart[n]
                st.rerun()
            c3.write(f"**{q}**")
            if c4.button("+", key=f"p{n}"):
                cart[n] += 1
                st.rerun()
        st.markdown(f"### الإجمالي: {total:g} ج.م")
        if st.button("✅ تأكيد البيع", type="primary"):
            now = datetime.now(TZ)
            inv = "F" + now.strftime("%y%m%d%H%M%S")
            ts = now.strftime("%Y-%m-%d %H:%M:%S")
            rows = [
                [inv, ts, n, int(q), float(price[n]), float(q * price[n])]
                for n, q in cart.items()
                if n in price
            ]
            add_sales(rows)
            st.session_state.cart = {}
            st.session_state.flash = f"تم تسجيل الفاتورة بإجمالي {total:g} ج.م"
            refresh()
        if st.button("مسح الفاتورة"):
            st.session_state.cart = {}
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
            refresh()


with tab_items:
    if st.button("➕ إضافة صنف", type="primary"):
        add_dialog()
    items = read_items()
    other = items[~items["category"].isin(CATS)]
    groups = [(c, items[items["category"] == c]) for c in CATS]
    if not other.empty:
        groups.append(("غير مصنف", other))
    for cat, sub in groups:
        with st.container(border=True):
            st.subheader(f"{cat} ({len(sub)})")
            if sub.empty:
                st.caption("لا توجد منتجات في هذا التصنيف")
            for r in sub.itertuples():
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
        s["total"] = pd.to_numeric(s["total"])
        s["qty"] = pd.to_numeric(s["qty"])
        s["day"] = s["dt"].dt.strftime("%Y-%m-%d")
        s["month"] = s["dt"].dt.strftime("%Y-%m")

        today = datetime.now(TZ).date()
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
            st.bar_chart(hours.reindex([f"{h:02d}" for h in range(24)], fill_value=0))
            st.subheader("أكتر الأصناف مبيعًا")
            top_items(df)
            st.subheader("الفواتير")
            if df.empty:
                st.write("لا فواتير.")
            for inv, g in df.groupby("invoice", sort=False):
                c1, c2 = st.columns([4, 1])
                desc = "، ".join(f"{r.item}×{r.qty}" for r in g.itertuples())
                c1.write(f"{g['dt'].iloc[0]:%H:%M} — {desc} — **{g['total'].sum():g} ج**")
                if c2.button("حذف", key=f"ds{inv}"):
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
