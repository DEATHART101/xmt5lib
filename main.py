import time
import MetaTrader5 as mt5
from strategies.price_bounce import PriceBounce

# === MT5 Connection ===
MT_PATH     = r"D:/Workspace/MT5/Instances/MetaTrader4/terminal64.exe"
MT_SERVER   = "MetaQuotes-Demo"
MT_ACCOUNT  = 103318004
MT_PASSWORD = "7nYxBs*j"

# === Strategy Config ===
SYMBOL         = "XAUUSD"
DIRECTION      = "LONG"   # "LONG" or "SHORT"
LOT_SIZE       = 0.01
CHECK_INTERVAL = 30        # seconds between each trading check (managed inside strategy)


def main():
    print(f"MT5 version: {mt5.version()}")

    if not mt5.initialize(login=MT_ACCOUNT, password=MT_PASSWORD,
                          server=MT_SERVER, portable=True):
        print(f"initialize() failed, error code = {mt5.last_error()}")
        return

    print(f"Connected. Strategy=PriceBounce | Symbol={SYMBOL} | Direction={DIRECTION} | Lot={LOT_SIZE}")

    strategy = PriceBounce(symbol=SYMBOL, lot_size=LOT_SIZE, tp_price=7.5,
                           check_interval=CHECK_INTERVAL)

    try:
        while True:
            strategy.set_direction(DIRECTION)
            strategy.on_tick()
            time.sleep(1)  # tight loop; interval logic is inside strategy
    except KeyboardInterrupt:
        print("Strategy stopped by user.")
    finally:
        mt5.shutdown()
        print("MT5 disconnected.")


if __name__ == "__main__":
    main()
