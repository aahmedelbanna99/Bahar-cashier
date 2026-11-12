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

st.set_page_config(page_title="نظام الكاشير", page_icon="🧾", layout="wide")
st.markdown(
    """<style>
.stApp,[data-testid="stDialog"]{direction:rtl}
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
