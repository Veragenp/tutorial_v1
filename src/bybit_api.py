from pybit.unified_trading import HTTP, WebSocket
import logging
import time
import requests

class BybitAPI:
    def __init__(self, api_key=None, api_secret=None):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Инициализация BybitAPI")
        self.session = HTTP(
            api_key=api_key,
            api_secret=api_secret,
            testnet=False
        )
        self.ws = WebSocket(testnet=False, channel_type="linear")
        self.logger.info("HTTP и WebSocket клиенты инициализированы")

    def get_last_7_days_high_low(self, symbol, days=7):
        """Получает high и low за последние 7 дней, исключая текущий день."""
        self.logger.debug(f"Запрос high/low для {symbol}, период: {days} дней")
        try:
            end_time = int(time.time() * 1000) - (86400 * 1000)
            start_time = end_time - (days * 86400 * 1000)
            self.logger.debug(f"start_time: {start_time}, end_time: {end_time}")
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval="D",
                start=start_time,
                end=end_time,
                limit=days
            )
            self.logger.debug(f"Ответ от get_kline: {response}")
            if response['retCode'] == 0 and response['result']['list']:
                candles = response['result']['list']
                candles.sort(key=lambda x: int(x[0]), reverse=True)
                result = [(float(candle[2]), float(candle[3])) for candle in candles]
                self.logger.info(f"Успешно получены high/low для {symbol}: {result}")
                return result
            self.logger.error(f"Ошибка получения исторических данных для {symbol}: {response['retMsg']}")
            return []
        except Exception as e:
            self.logger.error(f"Исключение при запросе исторических данных для {symbol}: {e}")
            return []

    def get_24h_volume(self, symbol):
        """Получает объём торгов за последние 24 часа в USDT."""
        self.logger.debug(f"Запрос объема торгов за 24 часа для {symbol}")
        try:
            base_url = "https://api.bybit.com"
            endpoint = "/v5/market/tickers"
            params = {"category": "linear", "symbol": symbol}
            self.logger.debug(f"GET запрос: {base_url + endpoint}, параметры: {params}")
            response = requests.get(base_url + endpoint, params=params)
            data = response.json()
            self.logger.debug(f"Ответ от API: {data}")
            if data["retCode"] == 0 and data["result"]["list"]:
                volume = float(data["result"]["list"][0]["turnover24h"])
                self.logger.info(f"Объем торгов за 24 часа для {symbol}: {volume} USDT")
                return volume
            self.logger.error(f"Не удалось получить объем для {symbol}: {data.get('retMsg', 'Нет данных')}")
            return 0
        except Exception as e:
            self.logger.error(f"Исключение при запросе объема для {symbol}: {e}")
            return 0

    def get_instrument_info(self, symbol):
        """Для populate_static_data.py."""
        self.logger.debug(f"Запрос информации об инструменте для {symbol}")
        try:
            response = self.session.get_instruments_info(category="linear", symbol=symbol)
            self.logger.debug(f"Ответ от get_instruments_info: {response}")
            if response['retCode'] == 0 and response['result']['list']:
                instrument_info = response['result']['list'][0]
                self.logger.info(f"Информация об инструменте {symbol} получена: {instrument_info}")
                return instrument_info
            self.logger.error(f"Не удалось получить информацию об инструменте {symbol}: {response.get('retMsg', 'Нет данных')}")
            return {}
        except Exception as e:
            self.logger.error(f"Исключение при получении информации об инструменте {symbol}: {e}")
            return {}

    def get_fee_rates(self, symbol):
        """Получает комиссии для символа."""
        self.logger.debug(f"Запрос комиссий для {symbol}")
        try:
            response = self.session.get_fee_rates(category="linear", symbol=symbol)
            self.logger.debug(f"Ответ от get_fee_rates: {response}")
            if response['retCode'] == 0 and response['result']['list']:
                fee_data = response['result']['list'][0]
                maker_fee = float(fee_data.get('makerFeeRate', 0))
                taker_fee = float(fee_data.get('takerFeeRate', 0))
                self.logger.info(f"Комиссии для {symbol}: maker_fee={maker_fee}, taker_fee={taker_fee}")
                return maker_fee, taker_fee
            self.logger.error(f"Не удалось получить комиссии для {symbol}: {response['retMsg']}")
            return 0, 0
        except Exception as e:
            self.logger.error(f"Исключение при запросе комиссий для {symbol}: {e}")
            return 0, 0

    def get_futures_instruments(self, limit=500):
        """Получает полный список фьючерсных инструментов с пагинацией."""
        self.logger.debug(f"Запрос списка фьючерсных инструментов, limit={limit}")
        try:
            all_symbols = []
            cursor = None
            while True:
                self.logger.debug(f"Запрос с cursor={cursor}")
                response = self.session.get_instruments_info(
                    category="linear",
                    limit=limit,
                    cursor=cursor
                )
                self.logger.debug(f"Ответ от get_instruments_info: {response}")
                if response['retCode'] != 0:
                    self.logger.error(f"Ошибка получения списка фьючерсов: {response['retMsg']}")
                    return all_symbols
                
                instruments = response['result']['list']
                symbols = [item['symbol'] for item in instruments]
                all_symbols.extend(symbols)
                cursor = response['result'].get('nextPageCursor')
                
                self.logger.info(f"Получено {len(instruments)} символов, всего: {len(all_symbols)}")
                if not cursor or len(instruments) < limit:
                    break
                time.sleep(0.1)
            
            self.logger.info(f"Всего получено {len(all_symbols)} фьючерсных инструментов")
            return all_symbols
        except Exception as e:
            self.logger.error(f"Исключение при запросе списка фьючерсов: {e}")
            return []

    def subscribe_to_ticker(self, symbols, callback):
        """Подписка на текущие цены через WebSocket."""
        self.logger.debug(f"Подписка на тикеры для символов: {symbols}")
        def handle_message(message):
            self.logger.debug(f"Получено WebSocket сообщение: {message}")
            if 'topic' in message and 'data' in message:
                symbol = message['topic'].split('.')[1]
                last_price = float(message['data']['lastPrice'])
                self.logger.info(f"Текущая цена для {symbol}: {last_price}")
                callback(symbol, last_price)

        for symbol in symbols:
            self.logger.debug(f"Подписка на тикер для {symbol}")
            self.ws.ticker_stream(symbol=symbol, callback=handle_message)

    def get_open_positions(self):
        """Возвращает количество открытых позиций."""
        self.logger.debug("Запрос количества открытых позиций")
        try:
            response = self.session.get_positions(category="linear", settleCoin="USDT")
            self.logger.debug(f"Ответ от get_positions: {response}")
            if response['retCode'] == 0:
                positions = [pos for pos in response['result']['list'] if float(pos['size']) > 0]
                self.logger.info(f"Открытых позиций: {len(positions)}")
                return len(positions)
            self.logger.error(f"Ошибка получения позиций: {response['retMsg']}")
            return 0
        except Exception as e:
            self.logger.error(f"Исключение при получении позиций: {e}")
            return 0

    def place_limit_order(self, symbol, side, qty, price, take_profit=None, stop_loss=None):
        """Размещает лимитный ордер."""
        self.logger.debug(f"Размещение ордера: symbol={symbol}, side={side}, qty={qty}, price={price}, "
                        f"take_profit={take_profit}, stop_loss={stop_loss}")
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
            self.logger.debug(f"Ответ от place_order: {response}")
            if response['retCode'] == 0:
                order_id = response['result']['orderId']
                self.logger.info(f"Ордер размещен: {order_id}")
                return order_id
            self.logger.error(f"Ошибка размещения ордера: {response['retMsg']}")
            return None
        except Exception as e:
            self.logger.error(f"Исключение при размещении ордера: {e}")
            return None

    def cancel_all_orders(self):
        """Отменяет все открытые ордеры."""
        self.logger.debug("Запрос на отмену всех открытых ордеров")
        try:
            response = self.session.cancel_all_orders(category="linear")
            self.logger.debug(f"Ответ от cancel_all_orders: {response}")
            if response['retCode'] == 0:
                self.logger.info(f"Все ордеры отменены: {len(response['result']['list'])} ордеров")
                return True
            self.logger.error(f"Ошибка отмены ордеров: {response['retMsg']}")
            return False
        except Exception as e:
            self.logger.error(f"Исключение при отмене ордеров: {e}")
            return False