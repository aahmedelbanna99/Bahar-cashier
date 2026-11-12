import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

TZ = ZoneInfo("Africa/Cairo")
SALES_COLS = ["invoice", "datetime", "item", "qty", "price", "total"]

st.set_page_config(page_title="نظام الكاشير", page_icon="🧾", layout="wide")
st.markdown(
    """<style>
.stApp{direction:rtl}
[data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.5rem}
[data-testid="stColumn"],[data-testid="column"]{min-width:28% !important;flex:1 1 28% !important}
.stButton button{width:100%;min-height:3rem}
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
    c.execute("create table if not exists items(id integer primary key autoincrement, name text, price real)")
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
        for name, head in (("items", ["name", "price"]), ("sales", SALES_COLS)):
            try:
                sh.worksheet(name)
            except gspread.WorksheetNotFound:
                sh.add_worksheet(name, rows=1000, cols=len(head)).append_row(head)
        return sh

    @st.cache_data(ttl=30)
    def sheet_read(name):
        rows = book().worksheet(name).get_all_records()
        cols = ["name", "price"] if name == "items" else SALES_COLS
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=cols)


def read_items():
    if SHEETS:
        df = sheet_read("items").copy()
        df["id"] = range(2, len(df) + 2)
        return df
    with conn() as c:
        return pd.read_sql("select id, name, price from items order by id", c)


def add_item(name, price):
    if SHEETS:
        book().worksheet("items").append_row([name, float(price)], value_input_option="RAW")
    else:
        with conn() as c:
            c.execute("insert into items(name, price) values(?, ?)", (name, float(price)))


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

tab_sale, tab_items, tab_rep = st.tabs(["البيع", "الأصناف", "التقارير"])

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

# ---------------- الأصناف ----------------
with tab_items:
    with st.form("add_item", clear_on_submit=True):
        n = st.text_input("اسم الصنف")
        p = st.number_input("السعر", min_value=0.0, step=0.5)
        if st.form_submit_button("إضافة صنف") and n.strip():
            add_item(n.strip(), p)
            refresh()
    items = read_items()
    st.subheader(f"الأصناف ({len(items)})")
    for r in items.itertuples():
        c1, c2 = st.columns([4, 1])
        c1.write(f"{r.name} — {r.price:g} ج")
        if c2.button("حذف", key=f"di{r.id}"):
            delete_item(r.id)
            refresh()

# ---------------- التقارير ----------------
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
        s["year"] = s["dt"].dt.strftime("%Y")

        today = datetime.now(TZ).date()
        day = st.date_input("اليوم", today).strftime("%Y-%m-%d")
        months = sorted(set(s["month"]) | {today.strftime("%Y-%m")})
        month = st.selectbox("الشهر", months, index=len(months) - 1)
        year = month[:4]

        m1, m2, m3, m4 = st.columns(4)
        for col, label, df in (
            (m1, "اليوم", s[s["day"] == day]),
            (m2, "الشهر", s[s["month"] == month]),
            (m3, f"سنة {year}", s[s["year"] == year]),
            (m4, "الإجمالي الكلي", s),
        ):
            col.metric(label, f"{df['total'].sum():,.2f} ج", f"{df['invoice'].nunique()} فاتورة", delta_color="off")

        days = pd.date_range(f"{month}-01", periods=pd.Period(month).days_in_month)
        per_day = s[s["month"] == month].groupby("day")["total"].sum()
        st.subheader("مبيعات أيام الشهر")
        st.bar_chart(per_day.reindex(days.strftime("%Y-%m-%d"), fill_value=0))

        per_month = s[s["year"] == year].groupby("month")["total"].sum()
        st.subheader(f"مبيعات شهور {year}")
        st.bar_chart(per_month.reindex([f"{year}-{k:02d}" for k in range(1, 13)], fill_value=0))

        st.subheader("أكتر الأصناف مبيعًا في الشهر")
        top = s[s["month"] == month].groupby("item")["qty"].sum().sort_values(ascending=False).head(10)
        st.dataframe(top.rename("الكمية"), use_container_width=True)

        st.subheader("فواتير اليوم المختار")
        day_df = s[s["day"] == day]
        if day_df.empty:
            st.write("لا فواتير.")
        for inv, g in day_df.groupby("invoice", sort=False):
            c1, c2 = st.columns([4, 1])
            desc = "، ".join(f"{r.item}×{r.qty}" for r in g.itertuples())
            c1.write(f"{g['dt'].iloc[0]:%H:%M} — {desc} — **{g['total'].sum():g} ج**")
            if c2.button("حذف", key=f"ds{inv}"):
                delete_invoice(inv)
                refresh()
