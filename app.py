import streamlit as st
import pandas as pd
import numpy as np
import io, re, textwrap
import matplotlib.pyplot as plt
from shared.parsing import parse_financials, compute_ratios, benchmark_for, BENCHMARKS, default_keywords
from parser_pdf import extract_tables_to_long
from export_docx import memo_to_docx

st.set_page_config(page_title="ClearPass Underwriting Suite", layout="wide")
st.title("🧮 ClearPass — Underwriting & Financial Health (Suite)")

left, right = st.columns([3,2], gap="large")

def ai_like_summary(company, industry, ratios):
    def strength(val, good, ok, inverse=False):
        if val is None: return 'n/a'
        if inverse:
            if val <= good: return 'strong'
            if val <= ok: return 'acceptable'
            return 'elevated'
        else:
            if val >= good: return 'strong'
            if val >= ok: return 'acceptable'
            return 'weak'
    cr = ratios.get('Current Ratio'); qr = ratios.get('Quick Ratio')
    de = ratios.get('Debt-to-Equity'); pm = ratios.get('Profit Margin (%)'); roa = ratios.get('Return on Assets (%)')
    cov = ratios.get('Interest Coverage (EBIT)') or ratios.get('Interest Coverage (EBITDA)')
    dscr = ratios.get('DSCR (CFO / Debt Service)')
    lines = []
    lines.append(f"Liquidity — Current {cr}, Quick {qr}. Position appears {strength(cr,1.8,1.2)} vs SME thresholds.")
    lines.append(f"Leverage — D/E {de}. Leverage is {strength(de,0.8,1.5,inverse=True)} vs peers.")
    lines.append(f"Profitability — Margin {pm}% and ROA {roa}%. Profitability is {strength(pm,12,6)} relative to medians.")
    if cov is not None:
        lines.append(f"Coverage — Interest coverage ≈ {cov}x ({ 'adequate' if cov and cov>=3 else 'tight'}).")
    if dscr is not None:
        lines.append(f"DSCR — {dscr}x based on CFO; ≥1.25x preferred for term debt.")
    lines.append("Overall — Balanced profile; focus on working capital discipline, sustainable leverage, and consistent cash generation.")
    return "\n".join(lines)

def underwriting_memo(company, year, industry, basics, ratios, bench):
    def fmt(val):
        if val is None or (isinstance(val,float) and pd.isna(val)): return 'n/a'
        try: return f'{float(val):,.0f}'
        except: return str(val)
    def rfmt(val, pct=False):
        if val is None or (isinstance(val,float) and pd.isna(val)): return 'n/a'
        return f'{val:,.2f}{ "%" if pct else "" }'
    sections = []
    sections.append(f'Underwriting Memo — {company} (FY {year})')
    sections.append(f'Industry: {industry}')
    sections.append('—'*60)
    cr = ratios.get('Current Ratio'); qr = ratios.get('Quick Ratio')
    de = ratios.get('Debt-to-Equity'); pm = ratios.get('Profit Margin (%)'); roa = ratios.get('Return on Assets (%)')
    cov = ratios.get('Interest Coverage (EBIT)') or ratios.get('Interest Coverage (EBITDA)')
    dscr = ratios.get('DSCR (CFO / Debt Service)')
    es = [
        f'Liquidity: Current {rfmt(cr)} (bench {bench["Current Ratio"]}), Quick {rfmt(qr)} (bench {bench["Quick Ratio"]}).',
        f'Leverage: D/E {rfmt(de)} (bench {bench["Debt-to-Equity"]}).',
        f'Profitability: Margin {rfmt(pm,True)} (bench {bench["Profit Margin (%)"]}%), ROA {rfmt(roa,True)} (bench {bench["Return on Assets (%)"]}%).',
        f'Coverage: Interest coverage ≈ {rfmt(cov)}x (target ≥3x).',
        f'DSCR: {rfmt(dscr)}x (preferred ≥1.25x)'
    ]
    sections.append('Executive Summary'); sections.append('\n'.join(es))
    fs = [
        f'Revenue: {fmt(basics.get("Revenue"))}',
        f'COGS: {fmt(basics.get("COGS"))}',
        f'Operating Expenses: {fmt(basics.get("Operating Expenses"))}',
        f'EBIT: {fmt(basics.get("EBIT"))}',
        f'EBITDA: {fmt(basics.get("EBITDA"))}',
        f'Net Income: {fmt(basics.get("Net Income"))}',
        f'Cash: {fmt(basics.get("Cash"))} | AR: {fmt(basics.get("Accounts Receivable"))} | Inventory: {fmt(basics.get("Inventory"))}',
        f'Current Assets: {fmt(basics.get("Current Assets"))} | Current Liabilities: {fmt(basics.get("Current Liabilities"))}',
        f'Total Liabilities: {fmt(basics.get("Total Liabilities"))} | Equity: {fmt(basics.get("Equity"))} | Total Assets: {fmt(basics.get("Total Assets"))}',
        f'CFO: {fmt(basics.get("CFO"))} | Interest Paid: {fmt(basics.get("Interest Paid"))} | Principal Repayment: {fmt(basics.get("Principal Repayment"))}',
        f'Interest Expense: {fmt(basics.get("Interest Expense"))}'
    ]
    sections.append('Financial Snapshot'); sections.append('\n'.join(fs))
    def lvl_de(d): 
        if d is None: return 'n/a'
        return 'conservative' if d<=1.0 else ('moderate' if d<=2.0 else 'elevated')
    cv = [
        f'Liquidity is {"strong" if cr and cr>=1.8 else ("acceptable" if cr and cr>=1.2 else "weak")} with working capital cover {rfmt(cr)}x.',
        f'Leverage is {lvl_de(de)} at D/E {rfmt(de)} relative to industry median {bench["Debt-to-Equity"]}.',
        f'Debt service capacity is {"adequate" if (cov is not None and cov>=3) else ("tight" if cov is not None else "n/a")} with coverage ≈ {rfmt(cov)}x; DSCR {rfmt(dscr)}x.',
        f'Profitability (margin {rfmt(pm,True)}, ROA {rfmt(roa,True)}) {"outperform" if (pm and pm>bench["Profit Margin (%)"]) else ("align with" if (pm and abs(pm-bench["Profit Margin (%)"])<=2) else "trail")} industry median.'
    ]
    sections.append('Credit View'); sections.append('\n'.join(cv))
    risks = [
        'Revenue/customer concentration may pressure cash flow in a downturn.',
        'Working capital strain if AR days extend or inventory turns slow.',
        'Exposure to rising rates on floating debt.'
    ]
    mitigants = [
        'Stable gross margins and positive CFO trend.',
        'Cash buffer; ability to flex SG&A if needed.',
        'Leverage within sector norms; coverage acceptable on base case.'
    ]
    sections.append('Key Risks'); sections.append('\n'.join([f'- {r}' for r in risks]))
    sections.append('Mitigants'); sections.append('\n'.join([f'- {m}' for m in mitigants]))
    sections.append('Indicative Decision Framework')
    dec = [
        '• Approve with standard terms if: D/E ≤ 1.5x and Interest coverage ≥ 3x and Current ratio ≥ 1.2x and DSCR ≥ 1.25x.',
        '• Approve with conditions (e.g., LOC) if: coverage 2.0–3.0x or current ratio 1.0–1.2x or DSCR 1.0–1.25x.',
        '• Decline or require collateral if: coverage < 2.0x or DSCR < 1.0x or severe liquidity stress.'
    ]
    sections.append('\n'.join(dec))
    return '\n\n'.join(sections)

with left:
    st.subheader("Upload Financials")
    files = st.file_uploader("Upload CSV/XLSX/PDF (multiple allowed).", type=["csv","xlsx","pdf"], accept_multiple_files=True)
    company = st.text_input("Company Name", "DemoCo Ltd.")
    fiscal_year = st.text_input("Fiscal Year", "2024")
    industry = st.selectbox("Industry", BENCHMARKS["industry_name"].tolist(), index=1)

    combined = []
    wide_candidate = None
    if files:
        for f in files:
            try:
                if f.name.lower().endswith(".pdf"):
                    df = extract_tables_to_long(f)
                elif f.name.lower().endswith(".csv"):
                    df = pd.read_csv(f)
                else:
                    df = pd.read_excel(f, sheet_name=0)
            except Exception as e:
                st.error(f"Could not read {f.name}: {e}"); continue
            if df.shape[1] >= 3:
                wide_candidate = df.copy()
            combined.append(df)

    if not combined:
        sample = pd.DataFrame({
            "Line Item":["Revenue","COGS","Operating Expenses","EBIT","Net Income","Cash","Accounts Receivable","Inventory","Current Assets","Current Liabilities","Total Liabilities","Equity","Total Assets","Interest Expense","Net cash provided by operating activities","Repayments of borrowings"],
            "2022":[1_000_000,600_000,250_000,150_000,90_000,50_000,40_000,30_000,150_000,80_000,220_000,300_000,520_000,20_000,85_000,15_000],
            "2023":[1_200_000,720_000,300_000,180_000,120_000,60_000,45_000,28_000,160_000,81_000,230_000,320_000,550_000,22_000,95_000,18_000],
            "2024":[1_350_000,800_000,335_000,215_000,150_000,62_000,50_000,25_000,170_000,85_000,240_000,340_000,580_000,24_000,110_000,20_000]
        })
        combined = [sample]; wide_candidate = sample

    merged = pd.concat(combined, ignore_index=True)
    st.markdown("**Preview**")
    st.dataframe(merged.head(25))

    basics, _ = parse_financials(merged, default_keywords())
    ratios = compute_ratios(basics)
    bench = benchmark_for(industry)

with right:
    st.subheader("Key Ratios")
    for k in ['Current Ratio','Quick Ratio','Debt-to-Equity','Profit Margin (%)','Return on Assets (%)','Interest Coverage (EBIT)','DSCR (CFO / Debt Service)']:
        st.metric(k, 'n/a' if ratios.get(k) is None else ratios[k])
    st.subheader("AI Health Summary")
    st.markdown(ai_like_summary(company, industry, ratios))

st.divider()
st.subheader("Trend Charts (if multi-year provided)")
if 'wide_candidate' in locals() and wide_candidate is not None:
    years = [c for c in wide_candidate.columns if re.search(r"20\d\d", str(c))]
    if len(years)>=2:
        out = []
        for y in years:
            dfy = wide_candidate[["Line Item", y]].rename(columns={"Line Item":"Account", y:"Value"})
            b, _ = parse_financials(dfy, default_keywords())
            r = compute_ratios(b)
            r["Year"] = y
            out.append(r)
        dfy = pd.DataFrame(out)
        for metric in ["Current Ratio","Debt-to-Equity","Profit Margin (%)"]:
            fig, ax = plt.subplots()
            ax.plot(dfy["Year"], dfy[metric], marker="o")
            ax.set_title(metric)
            st.pyplot(fig)

st.divider()
st.subheader("Exports")
col1, col2 = st.columns(2)
with col1:
    if st.button("Generate Underwriting PDF"):
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.pyplot as plt
        buf = io.BytesIO()
        with PdfPages(buf) as pdf:
            fig = plt.figure(figsize=(8.27, 11.69))
            ax = fig.add_axes([0,0,1,1]); ax.axis("off")
            ax.add_patch(plt.Rectangle((0,0.93), 1,0.07, transform=ax.transAxes))
            ax.text(0.30, 0.965, 'ClearPass — Underwriting Report', fontsize=18, weight='bold', transform=ax.transAxes, va='center')
            ax.text(0.08, 0.84, company, fontsize=24, weight='bold')
            ax.text(0.08, 0.80, f'Fiscal Year: {fiscal_year}', fontsize=11)
            ax.text(0.08, 0.77, f'Industry: {industry}', fontsize=11)
            pdf.savefig(fig); plt.close(fig)
            fig = plt.figure(figsize=(8.27, 11.69))
            ax = fig.add_axes([0.08,0.12,0.84,0.78]); ax.axis("off")
            ax.set_title("Key Ratios & Benchmarks", loc="left", fontsize=16, pad=10)
            rows = [
                ("Current Ratio", ratios.get("Current Ratio"), bench["Current Ratio"]),
                ("Quick Ratio", ratios.get("Quick Ratio"), bench["Quick Ratio"]),
                ("Debt-to-Equity", ratios.get("Debt-to-Equity"), bench["Debt-to-Equity"]),
                ("Profit Margin (%)", ratios.get("Profit Margin (%)"), bench["Profit Margin (%)"]),
                ("Return on Assets (%)", ratios.get("Return on Assets (%)"), bench["Return on Assets (%)"]),
                ("Interest Coverage (EBIT)", ratios.get("Interest Coverage (EBIT)"), "≥3.0x target"),
                ("Interest Coverage (EBITDA)", ratios.get("Interest Coverage (EBITDA)"), "≥3.0x target"),
                ("DSCR (CFO / Debt Service)", ratios.get("DSCR (CFO / Debt Service)"), "≥1.25x preferred"),
            ]
            y=0.95
            for name, val, b in rows:
                ax.text(0.02,y,f"{name}", fontsize=11)
                ax.text(0.55,y,f"{'n/a' if (val is None) else round(val,2)}", fontsize=11)
                ax.text(0.78,y,f"{'' if (b is None) else b}", fontsize=11)
                y -= 0.06
            pdf.savefig(fig); plt.close(fig)
            memo = underwriting_memo(company, fiscal_year, industry, basics, ratios, bench)
            fig = plt.figure(figsize=(8.27, 11.69))
            ax = fig.add_axes([0.08,0.08,0.84,0.84]); ax.axis("off")
            ax.set_title("Underwriting Memo", loc="left", fontsize=16, pad=10)
            wrapped = textwrap.fill(memo, 110)
            ax.text(0,1, wrapped, va="top", fontsize=10)
            pdf.savefig(fig); plt.close(fig)
        buf.seek(0)
        st.download_button("⬇️ Download PDF", data=buf, file_name=f"{company}_Underwriting_Report.pdf")

with col2:
    if st.button("Download DOCX Memo"):
        memo = underwriting_memo(company, fiscal_year, industry, basics, ratios, bench)
        out = io.BytesIO()
        tmp_path = f"/tmp/{company}_Underwriting_Memo.docx"
        memo_to_docx(memo, tmp_path)
        with open(tmp_path, "rb") as fh:
            out.write(fh.read())
        out.seek(0)
        st.download_button("⬇️ Download DOCX", data=out, file_name=f"{company}_Underwriting_Memo.docx")

st.divider()
st.subheader("Parsed Basics")
st.json({k:(None if (v is None or (isinstance(v,float) and np.isnan(v))) else float(v)) for k,v in basics.items()})
st.subheader("All Ratios")
st.json(ratios)
