from pybit.unified_trading import HTTP, WebSocket
import logging
import time
import requests

class BybitAPI:
    def __init__(self, api_key=None, api_secret=None):
        self.logger = logging.getLogger(__name__)
        self.session = HTTP(
            api_key=api_key,
            api_secret=api_secret,
            testnet=False
        )
        self.ws = WebSocket(testnet=False, channel_type="linear")

    def get_last_7_days_high_low(self, symbol, days=7):
        """Получает high и low за последние 7 дней, исключая текущий день."""
        try:
            end_time = int(time.time() * 1000) - (86400 * 1000)
            start_time = end_time - (days * 86400 * 1000)
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval="D",
                start=start_time,
                end=end_time,
                limit=days
            )
            if response['retCode'] == 0 and response['result']['list']:
                candles = response['result']['list']
                candles.sort(key=lambda x: int(x[0]), reverse=True)
                return [(float(candle[2]), float(candle[3])) for candle in candles]
            self.logger.error(f"Ошибка получения исторических данных для {symbol}: {response['retMsg']}")
            return []
        except Exception as e:
            self.logger.error(f"Ошибка при запросе исторических данных для {symbol}: {e}")
            return []

    def get_24h_volume(self, symbol):
        """Получает объём торгов за последние 24 часа в USDT."""
        try:
            base_url = "https://api.bybit.com"
            endpoint = "/v5/market/tickers"
            params = {"category": "linear", "symbol": symbol}
            response = requests.get(base_url + endpoint, params=params)
            data = response.json()
            if data["retCode"] == 0 and data["result"]["list"]:
                return float(data["result"]["list"][0]["turnover24h"])
            self.logger.error(f"Не удалось получить объем для {symbol}: {data.get('retMsg', 'Нет данных')}")
            return 0
        except Exception as e:
            self.logger.error(f"Ошибка при запросе объема для {symbol}: {e}")
            return 0

    def get_instrument_info(self, symbol):
        """Для populate_static_data.py."""
        try:
            response = self.session.get_instruments_info(category="linear", symbol=symbol)
            if response['retCode'] == 0 and response['result']['list']:
                return response['result']['list'][0]
            return {}
        except Exception as e:
            self.logger.error(f"Ошибка при получении информации об инструменте {symbol}: {e}")
            return {}

    def get_fee_rates(self, symbol):
        """Получает комиссии для символа."""
        try:
            response = self.session.get_fee_rates(category="linear", symbol=symbol)
            if response['retCode'] == 0 and response['result']['list']:
                fee_data = response['result']['list'][0]
                maker_fee = float(fee_data.get('makerFeeRate', 0))
                taker_fee = float(fee_data.get('takerFeeRate', 0))
                return maker_fee, taker_fee
            self.logger.error(f"Не удалось получить комиссии для {symbol}: {response['retMsg']}")
            return 0, 0
        except Exception as e:
            self.logger.error(f"Ошибка при запросе комиссий для {symbol}: {e}")
            return 0, 0

    def get_futures_instruments(self, limit=500):
        """Получает полный список фьючерсных инструментов с пагинацией."""
        try:
            all_symbols = []
            cursor = None
            while True:
                response = self.session.get_instruments_info(
                    category="linear",
                    limit=limit,
                    cursor=cursor
                )
                if response['retCode'] != 0:
                    self.logger.error(f"Ошибка получения списка фьючерсов: {response['retMsg']}")
                    return all_symbols
                
                instruments = response['result']['list']
                all_symbols.extend([item['symbol'] for item in instruments])
                cursor = response['result'].get('nextPageCursor')
                
                self.logger.info(f"Получено {len(instruments)} символов, всего: {len(all_symbols)}")
                if not cursor or len(instruments) < limit:
                    break
                time.sleep(0.1)
            
            self.logger.info(f"Всего получено {len(all_symbols)} фьючерсных инструментов")
            return all_symbols
        except Exception as e:
            self.logger.error(f"Ошибка при запросе списка фьючерсов: {e}")
            return []

    def subscribe_to_ticker(self, symbols, callback):
        """Подписка на текущие цены через WebSocket."""
        def handle_message(message):
            if 'topic' in message and 'data' in message:
                symbol = message['topic'].split('.')[1]
                last_price = float(message['data']['lastPrice'])
                callback(symbol, last_price)

        for symbol in symbols:
            self.ws.ticker_stream(symbol=symbol, callback=handle_message)

    def get_open_positions(self):
        """Возвращает количество открытых позиций."""
        try:
            response = self.session.get_positions(category="linear", settleCoin="USDT")
            if response['retCode'] == 0:
                positions = [pos for pos in response['result']['list'] if float(pos['size']) > 0]
                self.logger.info(f"Открытых позиций: {len(positions)}")
                return len(positions)
            self.logger.error(f"Ошибка получения позиций: {response['retMsg']}")
            return 0
        except Exception as e:
            self.logger.error(f"Ошибка при получении позиций: {e}")
            return 0

    def place_limit_order(self, symbol, side, qty, price, take_profit=None, stop_loss=None):
        """Размещает лимитный ордер."""
        try:
            response = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Limit",
                qty=str(qty),
                price=str(price),
                timeInForce="GTC",
                takeProfit=str(take_profit) if take_profit else None,
                stopLoss=str(stop_loss) if stop_loss else None
            )
            if response['retCode'] == 0:
                order_id = response['result']['orderId']
                self.logger.info(f"Ордер размещен: {order_id}")
                return order_id
            self.logger.error(f"Ошибка размещения ордера: {response['retMsg']}")
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при размещении ордера: {e}")
            return None

    def cancel_all_orders(self):
        """Отменяет все открытые ордеры."""
        try:
            response = self.session.cancel_all_orders(category="linear")
            if response['retCode'] == 0:
                self.logger.info(f"Все ордеры отменены: {len(response['result']['list'])} ордеров")
                return True
            self.logger.error(f"Ошибка отмены ордеров: {response['retMsg']}")
            return False
        except Exception as e:
            self.logger.error(f"Ошибка при отмене ордеров: {e}")
            return False