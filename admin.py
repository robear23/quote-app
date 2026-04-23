#!/usr/bin/env python3
"""Admin CLI for diagnosing user issues.

Usage:
  python admin.py list                   List all users
  python admin.py user <email>           Full user profile
  python admin.py quotes <email>         Last 10 generated quotes with line items
  python admin.py template <email>       Download quote templates to admin_downloads/
  python admin.py reset <email>          Reset bot_state to ACTIVE (unstick a user)
"""
import json
import os
import sys

from supabase import create_client
from config import settings

sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
TEMPLATES_BUCKET = settings.SUPABASE_TEMPLATES_BUCKET
DOWNLOAD_DIR = "admin_downloads"


def _find_user(email: str) -> dict | None:
    res = sb.table("users").select("*").eq("email", email.lower().strip()).execute()
    return res.data[0] if res.data else None


def _fmt(val) -> str:
    if val is None:
        return "—"
    if isinstance(val, dict):
        return json.dumps(val, indent=2)
    return str(val)


def cmd_user(email: str):
    user = _find_user(email)
    if not user:
        print(f"No user found for: {email}")
        return

    user_id = user["id"]
    print(f"\n{'='*60}")
    print(f"USER: {user.get('email')}")
    print(f"{'='*60}")
    print(f"  ID:           {user_id}")
    print(f"  Telegram ID:  {_fmt(user.get('telegram_id'))}")
    print(f"  Bot state:    {user.get('bot_state')}")
    print(f"  Tier:         {user.get('subscription_tier', 'free')}")
    print(f"  Created:      {str(user.get('created_at', ''))[:19]}")

    if user.get("pending_quote"):
        pq = user["pending_quote"]
        print(f"\n  PENDING QUOTE:")
        if isinstance(pq, dict):
            print(f"    Customer: {pq.get('customer_name')}")
            for item in pq.get("line_items", []):
                print(f"    - {item.get('description')} x{item.get('quantity')} @ {item.get('unit_price')}")
        else:
            print(f"    {pq}")

    cfg_res = sb.table("user_configs").select("*").eq("user_id", user_id).execute()
    if cfg_res.data:
        cfg = cfg_res.data[0]
        print(f"\n  CONFIG:")
        print(f"    Business:  {_fmt(cfg.get('business_name'))}")
        print(f"    Address:   {_fmt(cfg.get('business_address'))}")
        print(f"    Currency:  {_fmt(cfg.get('currency'))}")
        print(f"    VAT/Tax:   {_fmt(cfg.get('vat_tax_status'))}")
        print(f"    Format:    {_fmt(cfg.get('preferred_format'))}")
        print(f"    Template:  {_fmt(cfg.get('template_docx_path'))}")
        print(f"    Colors:    #{cfg.get('primary_color_hex') or '—'}  /  #{cfg.get('secondary_color_hex') or '—'}")
    else:
        print(f"\n  CONFIG: none (user hasn't completed onboarding)")

    docs_res = (
        sb.table("documents")
        .select("customer_name, total, created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )
    if docs_res.data:
        print(f"\n  RECENT QUOTES:")
        for doc in docs_res.data:
            print(f"    {str(doc.get('created_at', ''))[:19]}  {str(doc.get('customer_name', '?')):<30}  total={doc.get('total')}")
    else:
        print(f"\n  RECENT QUOTES: none")

    sub_res = (
        sb.table("subscriptions")
        .select("plan_tier, status, current_period_end")
        .eq("user_id", user_id)
        .execute()
    )
    if sub_res.data:
        sub = sub_res.data[0]
        end = str(sub.get("current_period_end", ""))[:10]
        print(f"\n  SUBSCRIPTION: {sub.get('plan_tier')} / {sub.get('status')}  (period ends {end})")

    print()


def cmd_quotes(email: str):
    user = _find_user(email)
    if not user:
        print(f"No user found for: {email}")
        return

    docs_res = (
        sb.table("documents")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    if not docs_res.data:
        print(f"No quotes found for {email}")
        return

    print(f"\n{'='*60}")
    print(f"QUOTES for {email}  ({len(docs_res.data)} shown)")
    print(f"{'='*60}")
    for doc in docs_res.data:
        print(f"\n  {str(doc.get('created_at', ''))[:19]}  —  {doc.get('customer_name')}")
        print(f"    Subtotal: {doc.get('subtotal')}  Tax: {doc.get('tax_amount')}  Total: {doc.get('total')}")
        for item in (doc.get("line_items") or []):
            print(f"    - {item.get('description')} x{item.get('quantity')} @ {item.get('unit_price')}")
    print()


def cmd_template(email: str):
    user = _find_user(email)
    if not user:
        print(f"No user found for: {email}")
        return

    user_id = user["id"]
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    for filename in ("quote_template.docx", "blank_template.docx"):
        path = f"templates/{user_id}/{filename}"
        try:
            data = sb.storage.from_(TEMPLATES_BUCKET).download(path)
            prefix = user_id[:8]
            out_path = os.path.join(DOWNLOAD_DIR, f"{prefix}_{filename}")
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"Downloaded: {out_path}")
        except Exception as e:
            print(f"  Could not download {filename}: {e}")


def cmd_reset(email: str):
    user = _find_user(email)
    if not user:
        print(f"No user found for: {email}")
        return

    print(f"Current state: {user.get('bot_state')}")
    confirm = input(f"Reset bot_state to ACTIVE and clear pending_quote for {email}? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    sb.table("users").update({"bot_state": "ACTIVE", "pending_quote": None}).eq("id", user["id"]).execute()
    print(f"Done — {email} is now in ACTIVE state.")


def cmd_list():
    users_res = (
        sb.table("users")
        .select("email, bot_state, subscription_tier, telegram_id, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    if not users_res.data:
        print("No users found.")
        return

    print(f"\n{'='*84}")
    print(f"{'EMAIL':<35} {'STATE':<22} {'TIER':<10} {'TELEGRAM':<12} JOINED")
    print(f"{'='*84}")
    for u in users_res.data:
        print(
            f"{str(u.get('email') or '?'):<35} "
            f"{str(u.get('bot_state') or '?'):<22} "
            f"{str(u.get('subscription_tier') or 'free'):<10} "
            f"{str(u.get('telegram_id') or '—'):<12} "
            f"{str(u.get('created_at', ''))[:10]}"
        )
    print()


USAGE = __doc__

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list()
    elif cmd == "user" and len(sys.argv) == 3:
        cmd_user(sys.argv[2])
    elif cmd == "quotes" and len(sys.argv) == 3:
        cmd_quotes(sys.argv[2])
    elif cmd == "template" and len(sys.argv) == 3:
        cmd_template(sys.argv[2])
    elif cmd == "reset" and len(sys.argv) == 3:
        cmd_reset(sys.argv[2])
    else:
        print(USAGE)
        sys.exit(1)
