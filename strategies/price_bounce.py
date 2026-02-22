from datetime import datetime
import MetaTrader5 as mt5

MAGIC = 20240101
PRICE_OFFSET = 0.2

class PriceBounce:
    def __init__(self, symbol: str, lot_size: float = 0.01, tp_price: float = 10):
        self.symbol = symbol
        self.lot_size = lot_size
        self.direction: str | None = None
        self.tp_price = tp_price

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

        if len(positions) > 0:
            for pos in positions:
                pos_is_long = pos.type == mt5.ORDER_TYPE_BUY
                dir_is_long = self.direction == "LONG"
                if pos_is_long != dir_is_long:
                    self._close_position(pos)
            return

        # No open positions: place a market order
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

        request = {
            "action":      mt5.TRADE_ACTION_DEAL,
            "symbol":      self.symbol,
            "volume":      self.lot_size,
            "type":        order_type,
            "price":       price,
            "sl":          sl,
            "tp":          tp,
            "deviation":   20,
            "magic":       MAGIC,
            "comment":     "PriceBounce",
            "type_time":   mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[{_now()}] order_send() failed: {result}")
        else:
            side = "BUY" if self.direction == "LONG" else "SELL"
            print(f"[{_now()}] {side} {self.lot_size} {self.symbol} @ {price}  SL={sl}  TP={tp}  ticket={result.order}")


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
