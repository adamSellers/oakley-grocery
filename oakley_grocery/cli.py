"""Unified CLI dispatcher for all oakley-grocery commands."""

import argparse
import sys


# ─── Phase 1: Setup & Status ────────────────────────────────────────────────

def cmd_setup(args):
    from oakley_grocery import auth

    if not args.woolworths_key and not args.woolworths_cookies:
        print("Error: Provide --woolworths-key and/or --woolworths-cookies.", file=sys.stderr)
        sys.exit(1)

    if args.woolworths_key:
        auth.save_woolworths_key(args.woolworths_key)
        print("Woolworths API key saved.")

        from oakley_grocery.woolworths import test_connection
        result = test_connection()
        if result["connected"]:
            print("Woolworths API: OK")
        else:
            print(f"Woolworths API: FAILED — {result['error']}")

    if args.woolworths_cookies:
        auth.save_woolworths_cookies(args.woolworths_cookies)
        print("Woolworths cookies saved.")

        from oakley_grocery.woolworths import validate_session
        result = validate_session()
        if result["valid"]:
            print("Woolworths session: OK")
        else:
            print(f"Woolworths session: INVALID — {result.get('error', 'unknown')}")


def cmd_status(args):
    from oakley_grocery import __version__, auth, db
    from oakley_grocery.common import Config, format_datetime_aest

    Config.ensure_dirs()

    lines = [
        f"Oakley Grocery v{__version__}",
        f"Time: {format_datetime_aest()}",
        "",
    ]

    # Woolworths API
    if auth.has_woolworths_key():
        from oakley_grocery.woolworths import test_connection
        result = test_connection()
        if result["connected"]:
            lines.append("Woolworths API: connected")
        else:
            lines.append(f"Woolworths API: DISCONNECTED — {result['error']}")
    else:
        lines.append("Woolworths API: not configured (search still works)")

    # Woolworths cookies
    if auth.has_woolworths_cookies():
        lines.append("Woolworths cart: cookies configured")
    else:
        lines.append("Woolworths cart: not configured (optional — for cart building)")

    # DB stats
    try:
        prefs = db.count_preferences()
        active_lists = db.count_lists("active")
        total_orders = db.count_orders()
        lines.append("")
        lines.append(f"Preferences: {prefs}")
        lines.append(f"Active lists: {active_lists}")
        lines.append(f"Orders: {total_orders}")
    except Exception:
        lines.append("")
        lines.append("Database: not initialized")

    lines.append("")
    lines.append(f"Data directory: {Config.data_dir}")

    print("\n".join(lines))


# ─── Phase 1: Search ────────────────────────────────────────────────────────

def cmd_search(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price
    from oakley_grocery import woolworths

    try:
        products = woolworths.search_products(
            query=args.query,
            page_size=args.limit,
            sort_by=args.sort or "",
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.specials_only:
        products = [p for p in products if p.get("on_special")]

    if not products:
        print("No products found.")
        return

    lines = [format_section_header(f"Woolworths Search: '{args.query}' ({len(products)} results)"), ""]

    for i, p in enumerate(products, 1):
        name = p.get("name", "Unknown")
        brand = p.get("brand", "")
        price = format_price(p.get("price"))
        size = p.get("package_size", "")
        cup = p.get("cup_string", "")

        line = f"{i}. {name}"
        if brand:
            line += f" ({brand})"
        lines.append(line)

        details = f"   {price}"
        if size:
            details += f" | {size}"
        if cup:
            details += f" | {cup}"

        if p.get("on_special"):
            was = format_price(p.get("was_price"))
            details += f" | SPECIAL (was {was})"

        if not p.get("available", True):
            details += " | UNAVAILABLE"

        lines.append(details)
        lines.append(f"   Code: {p.get('stockcode', 'N/A')}")
        lines.append("")

    print(truncate_for_telegram("\n".join(lines)))


# ─── Phase 2: Resolve ───────────────────────────────────────────────────────

def cmd_resolve(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price
    from oakley_grocery import resolver

    if args.stockcode:
        # Direct preference save
        from oakley_grocery import woolworths
        try:
            product = woolworths.get_product_details(args.stockcode)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if not product:
            print(f"Error: Product {args.stockcode} not found.", file=sys.stderr)
            sys.exit(1)

        resolver.learn_preference(
            generic_name=args.item,
            stockcode=args.stockcode,
            product_name=product.get("name", ""),
            brand=product.get("brand"),
            package_size=product.get("package_size"),
            price=product.get("price"),
        )
        print(f"Saved: '{args.item}' -> {product.get('name', 'Unknown')} ({format_price(product.get('price'))})")
        return

    result = resolver.resolve_item(
        generic_name=args.item,
        prefer_brand=args.brand,
        prefer_size=args.size,
    )

    if result["resolved"] and result["product"]:
        p = result["product"]
        lines = [
            format_section_header(f"Resolved: {args.item}"),
            "",
            f"Product: {p.get('name', 'Unknown')}",
            f"Price: {format_price(p.get('price'))}",
            f"Source: {result['source']}",
        ]
        if p.get("brand"):
            lines.append(f"Brand: {p['brand']}")
        if p.get("package_size"):
            lines.append(f"Size: {p['package_size']}")
        lines.append(f"Code: {p.get('stockcode', 'N/A')}")

        print(truncate_for_telegram("\n".join(lines)))
    elif result["candidates"]:
        lines = [
            format_section_header(f"Disambiguation needed: {args.item}"),
            "",
            "Pick one and run: oakley-grocery resolve --item ITEM --stockcode CODE",
            "",
        ]
        for i, c in enumerate(result["candidates"], 1):
            name = c.get("name", "Unknown")
            price = format_price(c.get("price"))
            brand = c.get("brand", "")
            size = c.get("package_size", "")
            score = c.get("_score", 0)

            line = f"{i}. {name}"
            if brand:
                line += f" ({brand})"
            lines.append(line)
            lines.append(f"   {price} | {size} | Score: {score:.2f}")
            lines.append(f"   Code: {c.get('stockcode', 'N/A')}")
            lines.append("")

        print(truncate_for_telegram("\n".join(lines)))
    else:
        print(f"Could not resolve '{args.item}'. Try searching: oakley-grocery search --query \"{args.item}\"")


# ─── Phase 2: List Commands ─────────────────────────────────────────────────

def cmd_list_create(args):
    from oakley_grocery import lists

    items = None
    if args.items:
        items = [i.strip() for i in args.items.split(",") if i.strip()]

    result = lists.create_list(args.name, items)
    print(f"Created list #{result['list_id']}: {result['name']} ({result['item_count']} items)")


def cmd_list_show(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price, format_shopping_list
    from oakley_grocery import lists

    try:
        data = lists.get_list(args.list_id, resolve=args.resolve)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    lst = data["list"]
    items = data["items"]
    stats = data["stats"]

    lines = [
        format_section_header(f"List #{lst['id']}: {lst['name']}"),
        f"Status: {lst['status']} | Items: {stats['total']}",
        f"Resolved: {stats['resolved']}/{stats['total']}",
        "",
    ]

    if items:
        lines.append(format_shopping_list(items))
    else:
        lines.append("(empty)")

    # Show disambiguation needed
    if stats.get("disambiguation_needed"):
        lines.append("")
        lines.append(format_section_header("Needs your pick:"))
        for d in stats["disambiguation_needed"]:
            lines.append(f"  {d['item']}:")
            for c in d["candidates"]:
                lines.append(f"    - {c['name']} ({format_price(c.get('price'))}) Code: {c['stockcode']}")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_list_add(args):
    from oakley_grocery import lists

    items = [i.strip() for i in args.items.split(",") if i.strip()]
    try:
        result = lists.add_items(args.list_id, items)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Added {result['added']} items, merged {result['merged']} duplicates.")


def cmd_list_remove(args):
    from oakley_grocery import lists

    items = [i.strip() for i in args.items.split(",") if i.strip()]
    try:
        result = lists.remove_items(args.list_id, items)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    msg = f"Removed {result['removed']} items."
    if result["not_found"]:
        msg += f" Not found: {', '.join(result['not_found'])}"
    print(msg)


def cmd_lists(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header
    from oakley_grocery import db

    all_lists = db.get_lists(status=args.status)

    if not all_lists:
        print("No lists found.")
        return

    label = args.status or "All"
    lines = [format_section_header(f"Shopping Lists — {label} ({len(all_lists)})"), ""]

    for lst in all_lists:
        items = db.get_list_items(lst["id"])
        resolved = sum(1 for i in items if i["resolved"])
        total = sum((i.get("price") or 0) * i.get("quantity", 1) for i in items if i.get("price"))

        status_badge = {
            "active": "",
            "purchased": " [PURCHASED]",
            "archived": " [ARCHIVED]",
        }.get(lst["status"], f" [{lst['status'].upper()}]")

        lines.append(f"#{lst['id']}: {lst['name']}{status_badge}")
        lines.append(f"  {len(items)} items ({resolved} resolved)")
        if total > 0:
            lines.append(f"  Est: ${total:.2f}")
        lines.append(f"  Created: {lst['created_at']}")
        lines.append("")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_list_clear(args):
    from oakley_grocery import db

    if not args.confirm:
        lst = db.get_list(args.list_id)
        if lst:
            print(f"Will delete list #{args.list_id}: {lst['name']}. Add --confirm to proceed.")
        else:
            print(f"List {args.list_id} not found.", file=sys.stderr)
            sys.exit(1)
        return

    if db.delete_list(args.list_id):
        print(f"Deleted list #{args.list_id}.")
    else:
        print(f"List {args.list_id} not found.", file=sys.stderr)
        sys.exit(1)


# ─── Phase 3: Cart & Checkout ───────────────────────────────────────────────

def cmd_cart_build(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price
    from oakley_grocery import cart

    result = cart.build_cart(args.list_id, confirm=args.confirm)

    if not result.get("success"):
        print(f"Error: {result.get('message', 'unknown error')}", file=sys.stderr)
        sys.exit(1)

    if result.get("preview"):
        lines = [
            format_section_header("Cart Preview"),
            "",
        ]
        for item in result["items"]:
            qty = item.get("quantity", 1)
            name = item.get("product_name", item["generic_name"])
            price = item.get("price")
            lines.append(f"  {qty}x {name} ({format_price(price)})")

        if result.get("unresolved"):
            lines.append("")
            lines.append(f"Unresolved ({len(result['unresolved'])}): {', '.join(result['unresolved'])}")

        lines.append("")
        lines.append(result["message"])
    else:
        lines = [
            format_section_header("Cart Built"),
            "",
            result["message"],
        ]
        if result.get("failed"):
            lines.append("")
            lines.append(f"Failed ({len(result['failed'])}):")
            for f in result["failed"]:
                lines.append(f"  {f['generic_name']}: {f['error']}")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_cart_status(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price
    from oakley_grocery import cart

    result = cart.get_cart_status()

    if not result.get("success"):
        print(f"Error: {result.get('message', 'unknown error')}", file=sys.stderr)
        sys.exit(1)

    if not result["items"]:
        print("Trolley is empty.")
        return

    lines = [format_section_header(f"Woolworths Trolley ({len(result['items'])} items)"), ""]

    for item in result["items"]:
        qty = item.get("quantity", 1)
        name = item.get("name", "Unknown")
        price = format_price(item.get("price"))
        total = format_price(item.get("total"))
        lines.append(f"  {qty}x {name} ({price} ea, {total})")

    lines.append("")
    lines.append(f"Total: {format_price(result['total'])}")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_checkout(args):
    print("To complete your order:")
    print("")
    print("1. Open: https://www.woolworths.com.au/shop/checkout")
    print("2. Review your trolley")
    print("3. Select delivery/pickup")
    print("4. Complete payment")
    print("")
    print("After checkout, run:")
    print("  oakley-grocery complete --list-id LIST_ID --total-paid AMOUNT --confirm")


def cmd_complete(args):
    from oakley_grocery.common import format_price
    from oakley_grocery import lists

    if not args.confirm:
        print(f"Will mark list #{args.list_id} as purchased.")
        if args.total_paid:
            print(f"Total paid: {format_price(args.total_paid)}")
        print("Add --confirm to proceed.")
        return

    try:
        result = lists.mark_purchased(
            list_id=args.list_id,
            total_paid=args.total_paid,
            notes=args.notes,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Order logged (#{result['order_id']}). {result['items_logged']} items recorded.")
    if args.total_paid:
        print(f"Total paid: {format_price(args.total_paid)}")


# ─── Phase 4: Intelligence ──────────────────────────────────────────────────

def cmd_usual(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price
    from oakley_grocery import memory, lists

    exclude = None
    if args.exclude:
        exclude = [e.strip() for e in args.exclude.split(",") if e.strip()]

    items = memory.build_usual(
        min_frequency=args.min_frequency,
        lookback_orders=args.lookback,
        exclude=exclude,
    )

    if not items:
        print("Not enough order history to build 'the usual'. Complete 3+ orders first.")
        return

    if args.create_list:
        from oakley_grocery.common.formatting import now_aest
        name = f"Weekly Shop {now_aest().strftime('%d %b')}"
        item_strings = [item["generic_name"] for item in items]
        result = lists.create_list(name, item_strings)
        print(f"Created list #{result['list_id']}: {name} ({result['item_count']} items)")
        print(f"Run: oakley-grocery list-show --list-id {result['list_id']} --resolve")
        return

    lines = [format_section_header(f"The Usual ({len(items)} items)"), ""]

    for item in items:
        name = item.get("generic_name", "?")
        freq = item.get("frequency", 0)
        product = item.get("product_name", "")
        avg = item.get("avg_price")

        line = f"  {name} (in {freq} of last orders)"
        if product and product != name:
            line += f" -> {product}"
        if avg:
            line += f" ~{format_price(avg)}"
        lines.append(line)

    lines.append("")
    lines.append("Add --create-list to make a shopping list from these items.")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_specials(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price
    from oakley_grocery import woolworths, db

    if args.usual_only:
        # Check specials for usual items
        usual_items = db.get_frequent_items(min_orders=2, lookback=10)
        if not usual_items:
            print("Not enough history. Complete a few orders first.")
            return

        stockcodes = {i.get("stockcode") for i in usual_items if i.get("stockcode")}
        if not stockcodes:
            print("No resolved products in your usual items.")
            return

        # Search for specials on those products
        matches = []
        for item in usual_items:
            if not item.get("stockcode"):
                continue
            try:
                product = woolworths.get_product_details(item["stockcode"])
                if product and product.get("on_special"):
                    matches.append({**product, "generic_name": item["generic_name"]})
            except RuntimeError:
                continue

        if not matches:
            print("None of your usual items are on special right now.")
            return

        lines = [format_section_header(f"Specials on Your Usual Items ({len(matches)})"), ""]
        for m in matches:
            name = m.get("name", m.get("generic_name", "?"))
            price = format_price(m.get("price"))
            was = format_price(m.get("was_price"))
            lines.append(f"  {name}")
            lines.append(f"    NOW {price} (was {was})")
            lines.append("")

        print(truncate_for_telegram("\n".join(lines)))
        return

    if args.for_list:
        # Check specials for items in a specific list
        items = db.get_list_items(args.for_list)
        if not items:
            print(f"List {args.for_list} is empty or not found.")
            return

        matches = []
        for item in items:
            if not item.get("stockcode"):
                continue
            try:
                product = woolworths.get_product_details(item["stockcode"])
                if product and product.get("on_special"):
                    matches.append({**product, "generic_name": item["generic_name"]})
            except RuntimeError:
                continue

        if not matches:
            print("No items in this list are on special.")
            return

        lines = [format_section_header(f"Specials in List #{args.for_list} ({len(matches)})"), ""]
        for m in matches:
            name = m.get("name", m.get("generic_name", "?"))
            price = format_price(m.get("price"))
            was = format_price(m.get("was_price"))
            lines.append(f"  {name}")
            lines.append(f"    NOW {price} (was {was})")
            lines.append("")

        print(truncate_for_telegram("\n".join(lines)))
        return

    # General specials
    try:
        products = woolworths.get_specials(page_size=args.limit)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not products:
        print("No specials found.")
        return

    lines = [format_section_header(f"Current Specials ({len(products)})"), ""]
    for i, p in enumerate(products, 1):
        name = p.get("name", "Unknown")
        price = format_price(p.get("price"))
        was = format_price(p.get("was_price"))
        lines.append(f"{i}. {name}")
        lines.append(f"   NOW {price} (was {was})")
        if p.get("cup_string"):
            lines.append(f"   {p['cup_string']}")
        lines.append(f"   Code: {p.get('stockcode', 'N/A')}")
        lines.append("")

    print(truncate_for_telegram("\n".join(lines)))


def cmd_prices(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price
    from oakley_grocery import db

    if args.item:
        # Look up preference to get stockcode
        pref = db.get_preference(args.item)
        if pref:
            history = db.get_price_history(stockcode=pref["stockcode"], days=args.days)
            if not history:
                print(f"No price history for '{args.item}'.")
                return

            lines = [format_section_header(f"Price History: {pref['product_name']}"), ""]
            for h in history:
                special = " *SPECIAL*" if h.get("on_special") else ""
                lines.append(f"  {h['recorded_at']}: {format_price(h['price'])}{special}")
            print(truncate_for_telegram("\n".join(lines)))
        else:
            print(f"No preference saved for '{args.item}'. Resolve it first.")
        return

    if args.all:
        history = db.get_price_history(days=args.days, limit=50)
        if not history:
            print("No price history recorded yet.")
            return

        lines = [format_section_header(f"Recent Prices (last {args.days} days)"), ""]
        for h in history:
            special = " *SPECIAL*" if h.get("on_special") else ""
            lines.append(f"  {h['product_name']}: {format_price(h['price'])}{special} ({h['recorded_at']})")
        print(truncate_for_telegram("\n".join(lines)))
        return

    print("Specify --item NAME or --all to view price history.")


def cmd_history(args):
    from oakley_grocery.common import truncate_for_telegram, format_section_header, format_price
    from oakley_grocery import db, memory

    orders = db.get_orders(limit=args.limit, days=args.days)

    if not orders:
        print("No purchase history.")
        return

    lines = [format_section_header(f"Purchase History ({len(orders)} orders)"), ""]

    for order in orders:
        paid = format_price(order.get("total_paid"))
        est = format_price(order.get("total_estimate"))
        items = order.get("item_count", 0)

        lines.append(f"Order #{order['id']} — {order['created_at']}")
        lines.append(f"  {items} items | Paid: {paid} | Est: {est}")
        if order.get("notes"):
            lines.append(f"  Note: {order['notes']}")
        lines.append("")

    # Add spending summary
    summary = memory.get_spending_summary(period_days=args.days or 30)
    if summary["order_count"] > 0:
        lines.append(f"Period total: {format_price(summary['total_spent'])}")
        lines.append(f"Avg order: {format_price(summary['avg_order'])}")

    print(truncate_for_telegram("\n".join(lines)))


# ─── Main dispatcher ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="oakley-grocery",
        description="Oakley Grocery — smart shopping list manager with Woolworths integration",
    )
    subparsers = parser.add_subparsers(dest="command")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Configure Woolworths credentials")
    setup_parser.add_argument("--woolworths-key", default=None, help="Woolworths API key (optional)")
    setup_parser.add_argument("--woolworths-cookies", default=None, help="Woolworths browser cookies (for cart)")

    # status
    subparsers.add_parser("status", help="Show version, API status, DB stats")

    # search
    search_parser = subparsers.add_parser("search", help="Search Woolworths products")
    search_parser.add_argument("--query", required=True, help="Search text")
    search_parser.add_argument("--sort", default=None, help="Sort: TraderRelevance|PriceAsc|PriceDesc")
    search_parser.add_argument("--specials-only", action="store_true", help="Only show items on special")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")

    # resolve
    resolve_parser = subparsers.add_parser("resolve", help="Resolve an item or save preference")
    resolve_parser.add_argument("--item", required=True, help="Generic item name (e.g. 'milk')")
    resolve_parser.add_argument("--brand", default=None, help="Preferred brand")
    resolve_parser.add_argument("--size", default=None, help="Preferred size")
    resolve_parser.add_argument("--stockcode", type=int, default=None, help="Save specific product as preference")

    # list-create
    lc_parser = subparsers.add_parser("list-create", help="Create a shopping list")
    lc_parser.add_argument("--name", required=True, help="List name")
    lc_parser.add_argument("--items", default=None, help="Comma-separated items (e.g. 'milk,bread,2 eggs')")

    # list-show
    ls_parser = subparsers.add_parser("list-show", help="Show a shopping list")
    ls_parser.add_argument("--list-id", type=int, required=True, help="List ID")
    ls_parser.add_argument("--resolve", action="store_true", help="Resolve unresolved items")

    # list-add
    la_parser = subparsers.add_parser("list-add", help="Add items to a list")
    la_parser.add_argument("--list-id", type=int, required=True, help="List ID")
    la_parser.add_argument("--items", required=True, help="Comma-separated items")

    # list-remove
    lr_parser = subparsers.add_parser("list-remove", help="Remove items from a list")
    lr_parser.add_argument("--list-id", type=int, required=True, help="List ID")
    lr_parser.add_argument("--items", required=True, help="Comma-separated item names")

    # lists
    lists_parser = subparsers.add_parser("lists", help="Show all lists")
    lists_parser.add_argument("--status", default=None, help="Filter: active|purchased|archived")

    # list-clear
    lcl_parser = subparsers.add_parser("list-clear", help="Delete a list")
    lcl_parser.add_argument("--list-id", type=int, required=True, help="List ID")
    lcl_parser.add_argument("--confirm", action="store_true", help="Actually delete")

    # cart-build
    cb_parser = subparsers.add_parser("cart-build", help="Build Woolworths cart from list")
    cb_parser.add_argument("--list-id", type=int, required=True, help="List ID")
    cb_parser.add_argument("--confirm", action="store_true", help="Actually add to trolley")

    # cart-status
    subparsers.add_parser("cart-status", help="Show current Woolworths trolley")

    # checkout
    subparsers.add_parser("checkout", help="Print checkout link and instructions")

    # complete
    comp_parser = subparsers.add_parser("complete", help="Mark list as purchased, log to history")
    comp_parser.add_argument("--list-id", type=int, required=True, help="List ID")
    comp_parser.add_argument("--total-paid", type=float, default=None, help="Amount actually paid")
    comp_parser.add_argument("--notes", default=None, help="Order notes")
    comp_parser.add_argument("--confirm", action="store_true", help="Actually complete")

    # usual
    usual_parser = subparsers.add_parser("usual", help="Generate 'the usual' list from history")
    usual_parser.add_argument("--min-frequency", type=int, default=0, help="Min order appearances (default: 3)")
    usual_parser.add_argument("--lookback", type=int, default=0, help="Orders to look back (default: 10)")
    usual_parser.add_argument("--exclude", default=None, help="Comma-separated items to exclude")
    usual_parser.add_argument("--create-list", action="store_true", help="Create a list from the usual")

    # specials
    spec_parser = subparsers.add_parser("specials", help="Check specials")
    spec_parser.add_argument("--for-list", type=int, default=None, help="Check specials for items in a list")
    spec_parser.add_argument("--usual-only", action="store_true", help="Only check your usual items")
    spec_parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # prices
    prices_parser = subparsers.add_parser("prices", help="Price history")
    prices_parser.add_argument("--item", default=None, help="Item name to check")
    prices_parser.add_argument("--all", action="store_true", help="Show all price history")
    prices_parser.add_argument("--days", type=int, default=90, help="Lookback period in days (default: 90)")

    # history
    hist_parser = subparsers.add_parser("history", help="Purchase history")
    hist_parser.add_argument("--limit", type=int, default=10, help="Max orders to show (default: 10)")
    hist_parser.add_argument("--days", type=int, default=None, help="Filter by recency (days)")

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "status": cmd_status,
        "search": cmd_search,
        "resolve": cmd_resolve,
        "list-create": cmd_list_create,
        "list-show": cmd_list_show,
        "list-add": cmd_list_add,
        "list-remove": cmd_list_remove,
        "lists": cmd_lists,
        "list-clear": cmd_list_clear,
        "cart-build": cmd_cart_build,
        "cart-status": cmd_cart_status,
        "checkout": cmd_checkout,
        "complete": cmd_complete,
        "usual": cmd_usual,
        "specials": cmd_specials,
        "prices": cmd_prices,
        "history": cmd_history,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
