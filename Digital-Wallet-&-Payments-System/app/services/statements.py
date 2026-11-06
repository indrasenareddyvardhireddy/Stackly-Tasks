import csv
import os
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import EntryType, LedgerEntry, Transaction, User, Wallet
from app.services.history import txn_dict
from app.utils.common import ZERO, month_start_utc, next_month, q2, to_ist


def parse_month(month: str):
    try:
        y, m = month.split("-")
        y, m = int(y), int(m)
        assert 2000 <= y <= 2100 and 1 <= m <= 12
        return y, m
    except Exception:
        raise HTTPException(422, "month must be in YYYY-MM format, e.g. 2026-10")


def build_statement(db: Session, user: User, wallet: Wallet, month: str) -> dict:
    y, m = parse_month(month)
    start, end = month_start_utc(y, m), month_start_utc(*next_month(y, m))
    acct = wallet.account
    prev = (db.query(LedgerEntry).filter(LedgerEntry.account_id == acct.id, LedgerEntry.created_at < start)
            .order_by(LedgerEntry.id.desc()).first())
    opening = prev.balance_after if prev else ZERO
    entries = (db.query(LedgerEntry).options(joinedload(LedgerEntry.transaction))
               .filter(LedgerEntry.account_id == acct.id, LedgerEntry.created_at >= start, LedgerEntry.created_at < end)
               .order_by(LedgerEntry.id).all())
    rows, credits, debits = [], ZERO, ZERO
    for e in entries:
        t = e.transaction
        d = txn_dict(t, wallet.id, e.balance_after)
        credit = e.amount if e.entry_type == EntryType.CREDIT else ZERO
        debit = e.amount if e.entry_type == EntryType.DEBIT else ZERO
        credits += credit
        debits += debit
        rows.append({"date": to_ist(e.created_at).strftime("%Y-%m-%d %H:%M"), "transaction_ref": t.transaction_ref,
                     "type": t.type.value, "other_party": d["other_party"]["name"], "status": t.status.value,
                     "debit": q2(debit), "credit": q2(credit), "balance_after": q2(e.balance_after)})
    closing = q2(opening + credits - debits)
    if entries and closing != q2(entries[-1].balance_after):
        raise HTTPException(500, "Statement integrity error: closing balance does not match the ledger")
    return {"wallet_number": wallet.wallet_number, "name": user.full_name, "month": month,
            "period": _period(month),
            "opening_balance": q2(opening), "total_credits": q2(credits), "total_debits": q2(debits),
            "closing_balance": closing, "rows": rows}


def _period(month: str) -> str:
    import calendar
    y, m = parse_month(month)
    last = calendar.monthrange(y, m)[1]
    return f"01-{m:02d}-{y} to {last:02d}-{m:02d}-{y}"


def _path(data: dict, ext: str, user_id: int) -> str:
    os.makedirs(settings.STATEMENTS_DIR, exist_ok=True)
    return os.path.join(settings.STATEMENTS_DIR, f"statement_{data['wallet_number']}_{data['month']}.{ext}")


def write_csv(data: dict, user_id: int) -> str:
    path = _path(data, "csv", user_id)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Wallet", data["wallet_number"]])
        w.writerow(["Name", data["name"]])
        w.writerow(["Period", _period(data["month"])])
        w.writerow(["Opening balance", data["opening_balance"]])
        w.writerow([])
        w.writerow(["Date", "Reference", "Type", "Other party", "Status", "Debit", "Credit", "Balance after"])
        for r in data["rows"]:
            w.writerow([r["date"], r["transaction_ref"], r["type"], r["other_party"], r["status"], r["debit"], r["credit"], r["balance_after"]])
        w.writerow([])
        w.writerow(["Total credits", data["total_credits"]])
        w.writerow(["Total debits", data["total_debits"]])
        w.writerow(["Closing balance", data["closing_balance"]])
    return path


def write_pdf(data: dict, user_id: int) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    path = _path(data, "pdf", user_id)
    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    el = [Paragraph("Wallet Statement", styles["Title"]),
          Paragraph(f"<b>Name:</b> {data['name']} &nbsp;&nbsp; <b>Wallet:</b> {data['wallet_number']} &nbsp;&nbsp; "
                    f"<b>Period:</b> {_period(data['month'])}", styles["Normal"]), Spacer(1, 6 * mm)]
    summary = Table([["Opening balance", "Total credits", "Total debits", "Closing balance"],
                     [f"Rs. {data['opening_balance']}", f"Rs. {data['total_credits']}",
                      f"Rs. {data['total_debits']}", f"Rs. {data['closing_balance']}"]], hAlign="LEFT")
    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                                 ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                 ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                 ("PADDING", (0, 0), (-1, -1), 5)]))
    el += [summary, Spacer(1, 6 * mm)]
    table_rows = [["Date (IST)", "Reference", "Type", "Other party", "Status", "Debit", "Credit", "Balance"]]
    for r in data["rows"]:
        table_rows.append([r["date"], r["transaction_ref"], r["type"], r["other_party"][:28], r["status"],
                           str(r["debit"]) if r["debit"] else "-", str(r["credit"]) if r["credit"] else "-",
                           str(r["balance_after"])])
    if len(table_rows) == 1:
        table_rows.append(["No transactions in this month", "", "", "", "", "", "", ""])
    t = Table(table_rows, repeatRows=1, colWidths=[32 * mm, 42 * mm, 34 * mm, 48 * mm, 20 * mm, 25 * mm, 25 * mm, 28 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fa")]),
                           ("ALIGN", (5, 0), (-1, -1), "RIGHT")]))
    el.append(t)
    doc.build(el)
    return path
