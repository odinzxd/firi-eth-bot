# Enkel Firi ETH daytrading-bot

Denne versjonen er med vilje enkel.

Markedsanalyse:
- Binance ETHUSDT
- 5 minutters candles
- EMA 9
- EMA 21
- RSI 14

Strategi:
- BUY: EMA9 > EMA21 og RSI 50–70
- SELL: EMA9 < EMA21
- TAKE PROFIT: +1.0 %
- STOP LOSS: -0.6 %

Firi:
- Ticker
- Balance
- Eventuell ordreutførelse

Standard:
- DRY_RUN=true
- Maks 10 handler per dag
- 10 minutters cooldown

Miljøvariabler:
DRY_RUN
FIRI_API_KEY
FIRI_CLIENT_ID
FIRI_SECRET_KEY
MARKET
MAX_TRADE_NOK
TEST_BUY_NOK
TEST_SELL_NOK
TEST_TRADE_PASSWORD
TEST_TRADING_ENABLED

Viktig:
Binance ETHUSDT brukes bare som retningsindikator. Faktisk handel skjer på Firi ETHNOK.
DRY_RUN bør brukes til testing før eventuell live trading.
