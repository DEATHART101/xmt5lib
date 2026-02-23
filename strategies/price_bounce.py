import time
from datetime import datetime
import MetaTrader5 as mt5

MAGIC = 20240101
PRICE_OFFSET = 0.2


class PriceBounce:
    def __init__(self, symbol: str, lot_size: float = 0.01, tp_price: float = 10,
                 check_interval: float = 30):
        self.symbol = symbol
        self.lot_size = lot_size
        self.direction: str | None = None
        self.tp_price = tp_price
        self.check_interval = check_interval

        self._last_price: float | None = None
        self._last_check_time: float | None = None

    def set_direction(self, direction: str):
        d = direction.upper()
        if d not in ("LONG", "SHORT"):
            raise ValueError(f"Invalid direction '{direction}'. Must be 'LONG' or 'SHORT'.")
        self.direction = d

    def set_tp_price(self, tp_price: float):
        self.tp_price = tp_price

    def on_tick(self):
        if self.direction is None:
            print(f"[{_now()}] direction not set, call set_direction() first.")
            return

        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            print(f"[{_now()}] positions_get() failed: {mt5.last_error()}")
            return

        # Always: if no open positions, cancel all pending orders (not interval-gated)
        if len(positions) == 0:
            self._cancel_all_pending_orders()

        # Interval gate for trading logic
        now = time.monotonic()
        if self._last_check_time is not None and (now - self._last_check_time) < self.check_interval:
            return
        self._last_check_time = now

        # Check direction reversal on open positions
        if len(positions) > 0:
            for pos in positions:
                pos_is_long = pos.type == mt5.ORDER_TYPE_BUY
                dir_is_long = self.direction == "LONG"
                if pos_is_long != dir_is_long:
                    self._close_position(pos)
            return

        # No open positions: check price momentum before placing order
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            print(f"[{_now()}] symbol_info_tick() failed: {mt5.last_error()}")
            return

        if self.direction == "LONG":
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
            sl    = price - PRICE_OFFSET
            tp    = price + self.tp_price
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
            sl    = price + PRICE_OFFSET
            tp    = price - self.tp_price

        last = self._last_price
        self._last_price = price

        if last is None:
            print(f"[{_now()}] first check, recording price={price}, waiting for next tick.")
            return

        if self.direction == "LONG" and price <= last:
            print(f"[{_now()}] LONG: price {price} <= last {last}, skip.")
            return
        if self.direction == "SHORT" and price >= last:
            print(f"[{_now()}] SHORT: price {price} >= last {last}, skip.")
            return

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       self.symbol,
            "volume":       self.lot_size,
            "type":         order_type,
            "price":        price,
            "sl":           sl,
            "tp":           tp,
            "deviation":    20,
            "magic":        MAGIC,
            "comment":      "PriceBounce",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[{_now()}] order_send() failed: {result}")
        else:
            side = "BUY" if self.direction == "LONG" else "SELL"
            print(f"[{_now()}] {side} {self.lot_size} {self.symbol} @ {price}  SL={sl}  TP={tp}  ticket={result.order}")
            self._place_pending_at_tp(price, tp)

    def _place_pending_at_tp(self, entry_price: float, tp_level: float):
        """Place a stop pending order at the TP level, same direction as current trade."""
        if self.direction == "LONG":
            pending_type = mt5.ORDER_TYPE_BUY_STOP
            pending_sl   = tp_level - PRICE_OFFSET
            pending_tp   = tp_level + self.tp_price
        else:
            pending_type = mt5.ORDER_TYPE_SELL_STOP
            pending_sl   = tp_level + PRICE_OFFSET
            pending_tp   = tp_level - self.tp_price

        request = {
            "action":       mt5.TRADE_ACTION_PENDING,
            "symbol":       self.symbol,
            "volume":       self.lot_size,
            "type":         pending_type,
            "price":        tp_level,
            "sl":           pending_sl,
            "tp":           pending_tp,
            "magic":        MAGIC,
            "comment":      "PriceBounce pending",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[{_now()}] pending order failed: {result}")
        else:
            side = "BUY STOP" if self.direction == "LONG" else "SELL STOP"
            print(f"[{_now()}] {side} pending @ {tp_level}  SL={pending_sl}  TP={pending_tp}  ticket={result.order}")

    def _cancel_all_pending_orders(self):
        orders = mt5.orders_get(symbol=self.symbol)
        if not orders:
            return
        for order in orders:
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order":  order.ticket,
            })
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"[{_now()}] cancel failed (ticket={order.ticket}): {result}")
            else:
                print(f"[{_now()}] cancelled pending ticket={order.ticket}")

    def _close_position(self, pos):
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            print(f"[{_now()}] symbol_info_tick() failed: {mt5.last_error()}")
            return

        close_type  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        close_price = tick.bid             if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       pos.symbol,
            "volume":       pos.volume,
            "type":         close_type,
            "position":     pos.ticket,
            "price":        close_price,
            "deviation":    20,
            "magic":        MAGIC,
            "comment":      "PriceBounce close",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[{_now()}] close failed (ticket={pos.ticket}): {result}")
        else:
            print(f"[{_now()}] closed ticket={pos.ticket} @ {close_price} (direction reversed)")


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")
