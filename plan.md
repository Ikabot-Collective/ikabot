# Auto Market Trader - Implementation Plan

## Overview
A new background module that automatically manages marketplace buy/sell orders across all 5 resources. It runs continuously, monitoring and refilling offers as they get fulfilled.

## Key Constraint
**One order type per resource**: Each resource can be either Buy (333) OR Sell (444), never both simultaneously. Different resources can have different types.

## Files to Create/Modify

### New File: `ikabot/function/autoMarketTrader.py`
Main module (~300 lines)

### Modified: `ikabot/command_line.py`
- Add import: `from ikabot.function.autoMarketTrader import autoMarketTrader`
- Add menu entry `803: autoMarketTrader` to `menu_actions`
- Add `"(3) Auto market trader"` under Marketplace submenu
- Change max from 2 to 3 in marketplace submenu read

### Modified: `ikabot/helpers/market.py`
- Add `getOwnOfferPrices(html)` - parse current prices from own offers form
- Add `getOwnOfferTradeTypes(html)` - parse current trade types (333/444)
- Add `getPriceLimits(html)` - parse min/max price boundaries per resource

---

## API Details (from HTML reference)

### POST `action=CityScreen&function=updateOffers`
Updates ALL 5 resources in one call:

| Parameter | Description | Values |
|---|---|---|
| `resourceTradeType` | Wood order type | 333=Buy, 444=Sell |
| `resource` | Wood amount | integer |
| `resourcePrice` | Wood price | integer (within limits) |
| `tradegood1TradeType` | Wine order type | 333/444 |
| `tradegood1` | Wine amount | integer |
| `tradegood1Price` | Wine price | integer |
| `tradegood2TradeType` | Marble order type | 333/444 |
| `tradegood2` | Marble amount | integer |
| `tradegood2Price` | Marble price | integer |
| `tradegood3TradeType` | Crystal order type | 333/444 |
| `tradegood3` | Crystal amount | integer |
| `tradegood3Price` | Crystal price | integer |
| `tradegood4TradeType` | Sulfur order type | 333/444 |
| `tradegood4` | Sulfur amount | integer |
| `tradegood4Price` | Sulfur price | integer |

Plus standard: `cityId`, `position`, `backgroundView=city`, `currentCityId`, `templateView=branchOfficeOwnOffers`, `currentTab=tab_branchOfficeOwnOffers`, `actionRequest`, `ajax=1`

### Constraints
- **Sell orders (444)**: Sum of ALL sell amounts <= `storageCapacity` (parsed from JS `var storageCapacity = N`)
- **Buy orders (333)**: Sum of (amount * price) for all buy orders <= available gold. Per-resource max = 40,000,000
- **Price limits**: Per-resource min/max from JS `'upper': N, 'lower': N` pattern

---

## Interactive Setup Flow

```
autoMarketTrader(session, event, stdin_fd, predetermined_input)
```

1. **Select marketplace city** - reuse `getCommercialCities()` + city picker
2. **Fetch marketplace state** - call `getMarketInfo()` to get own offers HTML
3. **Parse constraints** - storage capacity, price limits, gold, current offers
4. **For each resource (Wood, Wine, Marble, Crystal, Sulfur)**:
   - Show current offer status (if any)
   - Ask: `(0) Skip  (1) Buy  (2) Sell`
   - If Buy: ask amount (max 40M, limited by gold), ask price (within limits)
   - If Sell: ask amount (limited by storage capacity remaining + city resources), ask price (within limits)
5. **Ask mode**: `(1) Continuous - keep refilling forever  (2) Fixed total - stop after selling/buying X total`
   - If fixed: ask total amount per resource
6. **Ask poll interval**: minutes between checks (min 15, max 240, default 60)
7. **Summary & confirm**
8. **Launch background process**

---

## Background Loop Logic

```python
def run_auto_trader(session, city, trade_config, mode, interval_minutes):
    """
    trade_config: list of 5 dicts, one per resource:
      {
        "type": "444" | "333" | None,   # Sell, Buy, or Skip
        "amount": int,                   # Amount per refill cycle
        "price": int,                    # Price per unit
        "total": int | None,             # Total to trade (None = continuous)
        "traded_so_far": 0               # Running counter
      }
    """
```

### Each cycle:
1. **Fetch current state**: `getMarketInfo(session, city)` → own offers HTML
2. **Parse current amounts**: `onSellInMarket(html)` → [wood, wine, marble, crystal, sulfur] currently on marketplace
3. **Parse storage capacity**: `storageCapacityOfMarket(html)`
4. **Get gold balance**: `getGold(session, city)`
5. **Detect fulfilled trades**: Compare current amounts vs last known amounts
   - If sell amount decreased → someone bought from us
   - If buy amount decreased → someone sold to us
6. **Calculate new amounts** for each resource:
   - **Sell**: `new_amount = min(config.amount, storage_remaining, city_available_resources)`
   - **Buy**: `new_amount = min(config.amount, gold_affordable, 40_000_000)`
   - If fixed mode: cap at `total - traded_so_far`
7. **Build & send updateOffers POST** with all 5 resources
8. **Notify** if any trades were detected (resource name, amount traded, gold earned/spent)
9. **Update status line**: `session.setStatus(summary_string)`
10. **Check completion**: If all fixed-total resources are done, exit
11. **Sleep**: `wait(interval_minutes * 60)`

### Trade Detection Logic
```python
# For sell orders: if current_on_sell < previous_on_sell, items were bought
amount_sold = max(0, previous_amount - current_amount)

# For buy orders: if current_buy_amount < previous_buy_amount, items were delivered
amount_bought = max(0, previous_amount - current_amount)
```

After detecting trades, we set the new amount back up to the configured level (refill).

### Error Handling
- Wrap main loop in try/except, send error via `sendToBot()` on failure
- If `updateOffers` POST fails, retry once after 60s before notifying
- If gold runs out for buy orders, notify and set buy amount to 0 for that resource
- If city resources run out for sell orders, notify and set to 0, keep checking for restocks
- On any exception, log via `sendToBot()` and `session.logout()`

---

## New Helper Functions in `market.py`

```python
def getOwnOfferPrices(html):
    """Parse current prices from own offers form inputs.
    Returns list of 5 ints: [wood_price, wine_price, marble_price, crystal_price, sulfur_price]
    """
    # Price fields have maxlength="2" attribute which amount fields don't
    prices = re.findall(
        r'<input type="text" class="textfield"\s*size="\d+"\s*name=".*?Price"\s*id=".*?"\s*maxlength="\d+"\s*value="(\d+)"',
        html
    )
    return [int(p) for p in prices]


def getOwnOfferTradeTypes(html):
    """Parse current trade types from own offers dropdowns.
    Returns list of 5 strings: ["444", "333", ...] for each resource
    """
    types = re.findall(
        r'<select name="(?:resource|tradegood\d)TradeType".*?<option value="(\d+)" selected="">',
        html
    )
    return types


def getPriceLimits(html):
    """Parse min/max price boundaries per resource.
    Returns list of 5 tuples: [(min, max), ...]
    """
    limits = re.findall(r"'upper':\s*(\d+),\s*'lower':\s*(\d+)", html)
    return [(int(lo), int(hi)) for hi, lo in limits]
```

---

## Menu Integration

In `command_line.py`, marketplace submenu becomes:
```
(0) Back
(1) Buy resources
(2) Sell resources
(3) Auto market trader
```

---

## Process Info Signal

```python
info = "Auto Market Trader\n"
info += f"City: {city['name']}\n"
info += f"Interval: {interval_minutes} min\n"
for i, cfg in enumerate(trade_config):
    if cfg["type"]:
        action = "BUY" if cfg["type"] == "333" else "SELL"
        info += f"  {materials_names[i]}: {action} {cfg['amount']} @ {cfg['price']}\n"
setInfoSignal(session, info)
```

---

## Notification Format (on trade detection)

```
Auto Trader [{city_name}]:
  Sold 5,000 Wood @ 8 = 40,000 gold
  Wine buy order: 2,000 filled @ 10 = -20,000 gold
  Net gold: +20,000
  Offers refilled.
```

---

## Step-by-step Implementation Order

1. Add helper functions to `market.py` (getPriceLimits, getOwnOfferPrices, getOwnOfferTradeTypes)
2. Create `autoMarketTrader.py` with:
   a. Interactive setup function `autoMarketTrader()`
   b. Background worker function `run_auto_trader()`
   c. `buildUpdatePayload()` helper to construct the POST data
3. Register in `command_line.py` menu system
4. Test with existing reference HTML to verify regex patterns
