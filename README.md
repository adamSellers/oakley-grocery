# oakley-grocery

Smart grocery shopping CLI for Oakley — Woolworths product search, shopping lists with preference learning, cart building, and purchase intelligence.

## What It Does

- Search Woolworths products with prices, specials, and cup prices
- Build and manage shopping lists with quantity parsing ("2 milk", "bread x3")
- Resolve generic items to specific products with a learning preference engine
- Build Woolworths cart from resolved lists (you tap checkout)
- Track purchase history and price trends
- Generate "the usual" list from order patterns
- Check specials on your regular items

Checkout is manual — this skill builds the cart, you complete payment in the Woolworths app/website. The compound value is in preference learning: after 3-4 shops, "do the usual" builds a fully-resolved cart in seconds.

## Install

```bash
cd oakley-grocery
python3 -m pip install .
```

CLI installs to `~/.local/bin/oakley-grocery`.

## Setup

```bash
# Optional — search works without auth
oakley-grocery setup --woolworths-key YOUR_KEY

# Required for cart operations — cookies from logged-in browser session
oakley-grocery setup --woolworths-cookies "COOKIE_STRING"

# Verify
oakley-grocery status
```

## Quick Start

```bash
# Search for products
oakley-grocery search --query "milk"

# Create a shopping list
oakley-grocery list-create --name "Weekly Shop" --items "milk,bread,2 eggs,chicken"

# Resolve items to specific products
oakley-grocery list-show --list-id 1 --resolve

# Save a product preference
oakley-grocery resolve --item "milk" --stockcode 123456

# Build Woolworths cart
oakley-grocery cart-build --list-id 1           # preview
oakley-grocery cart-build --list-id 1 --confirm # add to trolley

# After checkout
oakley-grocery complete --list-id 1 --total-paid 92.30 --confirm

# Next time — instant
oakley-grocery usual --create-list
```

## Commands

| Command | Description |
|---------|-------------|
| `setup` | Configure Woolworths credentials |
| `status` | Version, API status, DB stats |
| `search` | Search Woolworths products |
| `resolve` | Resolve item or save preference |
| `list-create` | Create a shopping list |
| `list-show` | Show list with optional resolution |
| `list-add` | Add items to a list |
| `list-remove` | Remove items from a list |
| `lists` | Show all lists |
| `list-clear` | Delete a list |
| `cart-build` | Build Woolworths cart from list |
| `cart-status` | Show current trolley |
| `checkout` | Print checkout link |
| `complete` | Mark purchased, log to history |
| `usual` | Generate "the usual" from history |
| `specials` | Check specials for your items |
| `prices` | Price history for tracked items |
| `history` | Purchase history |

## Deploy

```bash
# Push to git, then on device:
ssh oakley@bot.oakroad
cd /home/oakley/.openclaw/workspace/skills/oakley-grocery
git pull
pipx install . --force
```

## Tests

```bash
python3 -m pytest tests/ -v
```

94 tests covering formatting, DB CRUD, Woolworths product parsing, resolver scoring/matching, shopping lists, and purchase memory.
