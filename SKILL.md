# Oakley Grocery

Smart grocery shopping assistant — Woolworths product search, shopping lists with preference learning, cart building, and purchase intelligence.

## What It Does

- Search Woolworths products (prices, specials, cup prices)
- Build and manage shopping lists
- Resolve generic items ("milk") to specific products with preference learning
- Build Woolworths cart from resolved lists (you tap checkout)
- Track purchase history and prices
- Generate "the usual" list from order patterns
- Check specials on your regular items

## Important

- **Checkout is manual** — this skill builds the cart, you complete payment in the Woolworths app/website
- **Preferences get smarter over time** — after 3-4 shops, "do the usual" builds a fully-resolved cart in seconds
- **Cart building requires cookies** — captured from a logged-in Woolworths browser session. Expires periodically.
- Search works without any setup. Cart operations need cookies.

## Commands

### Setup & Status

```bash
# Save Woolworths API key (optional — search works without it)
exec oakley-grocery setup --woolworths-key KEY

# Save cookies for cart operations (captured from browser)
exec oakley-grocery setup --woolworths-cookies "COOKIE_STRING"

# Check version, API status, DB stats
exec oakley-grocery status
```

### Product Search

```bash
# Search for products
exec oakley-grocery search --query "full cream milk"

# Sort by price
exec oakley-grocery search --query "chicken breast" --sort PriceAsc

# Only show specials
exec oakley-grocery search --query "yoghurt" --specials-only

# More results
exec oakley-grocery search --query "bread" --limit 20
```

### Product Resolution & Preferences

```bash
# Resolve a generic name to a specific product
exec oakley-grocery resolve --item "milk"

# Resolve with brand/size preference
exec oakley-grocery resolve --item "milk" --brand "Pauls" --size "2L"

# Save a specific product as the preference for an item
exec oakley-grocery resolve --item "milk" --stockcode 123456
```

When the agent asks "which milk?" — present the candidates to Adam, then save his choice with `--stockcode`.

### Shopping Lists

```bash
# Create a list
exec oakley-grocery list-create --name "Weekly Shop"

# Create with initial items
exec oakley-grocery list-create --name "Weekly Shop" --items "milk,bread,2 eggs,chicken"

# Add items to a list (quantities: "2 milk" or "milk")
exec oakley-grocery list-add --list-id 1 --items "butter,cheese,3 bananas"

# Remove items
exec oakley-grocery list-remove --list-id 1 --items "butter,cheese"

# Show list (with current resolution status)
exec oakley-grocery list-show --list-id 1

# Show list and resolve unresolved items
exec oakley-grocery list-show --list-id 1 --resolve

# Show all lists
exec oakley-grocery lists
exec oakley-grocery lists --status active

# Delete a list
exec oakley-grocery list-clear --list-id 1 --confirm
```

### Cart Building

```bash
# Preview what would be added to cart
exec oakley-grocery cart-build --list-id 1

# Actually build the cart (adds to Woolworths trolley)
exec oakley-grocery cart-build --list-id 1 --confirm

# Check current trolley
exec oakley-grocery cart-status

# Get checkout instructions
exec oakley-grocery checkout
```

### Completing an Order

After Adam checks out manually:

```bash
# Mark list as purchased and log to history
exec oakley-grocery complete --list-id 1 --total-paid 92.30 --confirm
```

This updates preferences, records prices, and logs the order for future "usual" generation.

### The Usual

```bash
# Show items that appear in 3+ of last 10 orders
exec oakley-grocery usual

# Create a list from the usual
exec oakley-grocery usual --create-list

# Customize frequency threshold
exec oakley-grocery usual --min-frequency 2 --lookback 5

# Exclude items
exec oakley-grocery usual --exclude "chips,chocolate"
```

### Specials

```bash
# Browse current specials
exec oakley-grocery specials

# Check specials for items in a list
exec oakley-grocery specials --for-list 1

# Check specials only for your usual items
exec oakley-grocery specials --usual-only
```

### Price History

```bash
# Price history for a specific item
exec oakley-grocery prices --item "milk"

# All recent prices
exec oakley-grocery prices --all --days 30
```

### Purchase History

```bash
# Recent orders
exec oakley-grocery history

# Last 5 orders
exec oakley-grocery history --limit 5

# Orders from last 7 days
exec oakley-grocery history --days 7
```

## Typical Flow

1. **Adam says**: "Add milk, bread, and eggs to the shopping list"
2. **Agent**: Creates list, adds items → `list-create --name "Shopping" --items "milk,bread,eggs"`
3. **Agent**: Shows list with resolution → `list-show --list-id 1 --resolve`
4. **If disambiguation needed**: Agent presents options, Adam picks → `resolve --item "milk" --stockcode 123`
5. **Adam says**: "Build the cart"
6. **Agent**: Preview → `cart-build --list-id 1`, then confirm → `cart-build --list-id 1 --confirm`
7. **Adam**: Opens Woolworths app, taps checkout
8. **Adam says**: "Done, paid $92.30"
9. **Agent**: `complete --list-id 1 --total-paid 92.30 --confirm`

Next time: "Do the usual" → `usual --create-list` → instant resolved list.

## Error Handling

- If Woolworths search fails, the skill returns stale cached results (up to 24hr)
- If cart building fails for individual items, it continues with the rest and reports failures
- If cookies expire, the skill tells you to update them
- All network calls have 10s timeouts
- Rate limited at 5 req/sec to Woolworths

## Cron

No cron jobs. All operations are on-demand via the agent.
