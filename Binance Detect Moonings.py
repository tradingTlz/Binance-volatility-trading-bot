# use for environment variables
import os

# Needed for colorful console output Install with: python3 -m pip install colorama (Mac/Linux) or pip install colorama (PC)
from colorama import init
init()

# needed for the binance API and websockets
from binance.client import Client

# used for dates
from datetime import datetime, timedelta
import time

# used to repeatedly execute the code
from itertools import count

# used to store trades and sell assets
import json

# Switch between testnet and mainnet
# Setting this to False will use REAL funds, use at your own risk
# Define your API keys below in order for the toggle to work
TESTNET = True


# Get binance key and secret for TEST and MAINNET
# The keys below are pulled from environment variables using os.getenv
# Simply remove this and use the following format instead: api_key_test = 'YOUR_API_KEY'
api_key_test = 'abff4REVFtxpQSp9k0SCrKchT1qk7nrGisFNbZyo1eD5Td6oMw40aHeEr5uBb3et'
api_secret_test = 'fiTU84rNtofWYjO3Tqa4K4HG9xVqWseMfHRO5tptJuud8HRtEL5zWs60oJM1EEUM'
# api_key_test = os.getenv('binance_api_stalkbot_testnet')
# api_secret_test = os.getenv('binance_secret_stalkbot_testnet')

api_key_live = os.getenv('binance_api_stalkbot_live')
api_secret_live = os.getenv('binance_secret_stalkbot_live')


# Authenticate with the client
if TESTNET:
    client = Client(api_key_test, api_secret_test)

    # The API URL needs to be manually changed in the library to work on the TESTNET
    client.API_URL = 'https://testnet.binance.vision/api'

else:
    client = Client(api_key_live, api_secret_live)


####################################################
#                   USER INPUTS                    #
# You may edit to adjust the parameters of the bot #
####################################################


# select what to pair the coins to and pull all coins paired with PAIR_WITH
PAIR_WITH = 'USDT'

# Define the size of each trade, by default in USDT
QUANTITY = 15

# Define max numbers of coins to hold
MAX_COINS = 10

# List of pairs to exclude
# by default we're excluding the most popular fiat pairs
# and some margin keywords, as we're only working on the SPOT account
FIATS = ['EURUSDT', 'GBPUSDT', 'JPYUSDT', 'USDUSDT', 'DOWN', 'UP']

# the amount of time in SECONDS to calculate the differnce from the current price
TIME_DIFFERENCE = 1/60

# Numer of times to check for TP/SL during each TIME_DIFFERENCE Minimum 1
RECHECK_INTERVAL = 6

# the difference in % between the first and second checks for the price.
CHANGE_IN_PRICE = 1.25

# define in % when to sell a coin that's not making a profit
STOP_LOSS = 1.75

# define in % when to take profit on a profitable coin
TAKE_PROFIT = 3

# whether to use trailing stop loss or not; default is True
USE_TRAILING_STOP_LOSS = True

# when hit TAKE_PROFIT, move STOP_LOSS to TRAILING_STOP_LOSS percentage points below TAKE_PROFIT hence locking in profit
# when hit TAKE_PROFIT, move TAKE_PROFIT up by TRAILING_TAKE_PROFIT percentage points
TRAILING_STOP_LOSS = 2
TRAILING_TAKE_PROFIT = 2

# Use custom tickers.txt list for filtering pairs
CUSTOM_LIST = False

# Use log file for trades
LOG_TRADES = True
LOG_FILE = 'trades.txt'

# Debug for additional console output
DEBUG = True


####################################################
#                END OF USER INPUTS                #
#                  Edit with care                  #
####################################################




# for colourful logging to the console
class txcolors:
    BUY = '\033[92m'
    WARNING = '\033[93m'
    SELL = '\033[91m'
    DEFAULT = '\033[39m'

# Use CUSTOM_LIST symbols if CUSTOM_LIST is set to True
if CUSTOM_LIST: tickers=[line.strip() for line in open('tickers.txt')]

# try to load all the coins bought by the bot if the file exists and is not empty
coins_bought = {}

# path to the saved coins_bought file
coins_bought_file_path = 'coins_bought.json'

# use separate files for testnet and live
if TESTNET:
    coins_bought_file_path = 'testnet_' + coins_bought_file_path

# if saved coins_bought json file exists and it's not empty then load it
if os.path.isfile(coins_bought_file_path) and os.stat(coins_bought_file_path).st_size!= 0:
    with open(coins_bought_file_path) as file:
            coins_bought = json.load(file)


def get_price():
    '''Return the current price for all coins on binance'''

    initial_price = {}
    prices = client.get_all_tickers()

    for coin in prices:

        if CUSTOM_LIST:
            if any(item + PAIR_WITH == coin['symbol'] for item in tickers) and all(item not in coin['symbol'] for item in FIATS):
                initial_price[coin['symbol']] = { 'price': coin['price'], 'time': datetime.now()}
        else:
            if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in FIATS):
                initial_price[coin['symbol']] = { 'price': coin['price'], 'time': datetime.now()}

    return initial_price


def wait_for_price():
    '''calls the initial price and ensures the correct amount of time has passed
    before reading the current price again'''

    volatile_coins = {}
    initial_price = get_price()

    while initial_price['BNB' + PAIR_WITH]['time'] > datetime.now() - timedelta(seconds=TIME_DIFFERENCE):
        i=0
        while i < RECHECK_INTERVAL:
            print(f'checking TP/SL...')
            coins_sold = sell_coins()
            remove_from_portfolio(coins_sold)
            time.sleep((TIME_DIFFERENCE/RECHECK_INTERVAL))
            i += 1
            # let's wait here until the time passess...

        print(f'not enough time has passed yet...')

    else:
        last_price = get_price()
        infoChange = -100.00
        infoCoin = 'none'
        infoStart = 0.00
        infoStop = 0.00

        # calculate the difference between the first and last price reads
        for coin in initial_price:
            threshold_check = (float(last_price[coin]['price']) - float(initial_price[coin]['price'])) / float(initial_price[coin]['price']) * 100

            if threshold_check > infoChange:
                infoChange = threshold_check
                infoCoin = coin
                infoStart = initial_price[coin]['price']
                infoStop = last_price[coin]['price']

            # each coin with higher gains than our CHANGE_IN_PRICE is added to the volatile_coins dict if less than MAX_COINS is not reached.
            if threshold_check > CHANGE_IN_PRICE:
                if len(coins_bought) < MAX_COINS:
                    volatile_coins[coin] = threshold_check
                    volatile_coins[coin] = round(volatile_coins[coin], 3)
                    print(f'{coin} has gained {volatile_coins[coin]}% in the last {TIME_DIFFERENCE} seconds, calculating volume in {PAIR_WITH}')

                else:
                    print(f'{txcolors.WARNING}{coin} has gained {threshold_check}% in the last {TIME_DIFFERENCE} seconds, but you are holding max number of coins{txcolors.DEFAULT}')

        # Print more info if there are no volatile coins this iteration
        if infoChange < CHANGE_IN_PRICE:
                print(f'No coins moved more than {CHANGE_IN_PRICE}% in the last {TIME_DIFFERENCE} second(s)')

        print(f'Max movement {float(infoChange):.2f}% by {infoCoin} from {float(infoStart):.4f} to {float(infoStop):.4f}')

        return volatile_coins, len(volatile_coins), last_price


def convert_volume():
    '''Converts the volume given in QUANTITY from USDT to the each coin's volume'''

    volatile_coins, number_of_coins, last_price = wait_for_price()
    lot_size = {}
    volume = {}

    for coin in volatile_coins:

        # Find the correct step size for each coin
        # max accuracy for BTC for example is 6 decimal points
        # while XRP is only 1
        try:
            info = client.get_symbol_info(coin)
            step_size = info['filters'][2]['stepSize']
            lot_size[coin] = step_size.index('1') - 1

            if lot_size[coin] < 0:
                lot_size[coin] = 0

        except:
            pass

        # calculate the volume in coin from QUANTITY in USDT (default)
        volume[coin] = float(QUANTITY / float(last_price[coin]['price']))

        # define the volume with the correct step size
        if coin not in lot_size:
            volume[coin] = float('{:.1f}'.format(volume[coin]))

        else:
            # if lot size has 0 decimal points, make the volume an integer
            if lot_size[coin] == 0:
                volume[coin] = int(volume[coin])
            else:
                volume[coin] = float('{:.{}f}'.format(volume[coin], lot_size[coin]))

    return volume, last_price


def buy():
    '''Place Buy market orders for each volatile coin found'''

    volume, last_price = convert_volume()
    orders = {}

    for coin in volume:

        # only buy if the there are no active trades on the coin
        if coin not in coins_bought:
            print(f"{txcolors.BUY}Preparing to buy {volume[coin]} {coin}{txcolors.DEFAULT}")

            if TESTNET :
                # create test order before pushing an actual order
                test_order = client.create_test_order(symbol=coin, side='BUY', type='MARKET', quantity=volume[coin])

            # try to create a real order if the test orders did not raise an exception
            try:
                buy_limit = client.create_order(
                    symbol = coin,
                    side = 'BUY',
                    type = 'MARKET',
                    quantity = volume[coin]
                )

            # error handling here in case position cannot be placed
            except Exception as e:
                print(e)

            # run the else block if the position has been placed and return order info
            else:
                orders[coin] = client.get_all_orders(symbol=coin, limit=1)

                # binance sometimes returns an empty list, the code will wait here until binance returns the order
                while orders[coin] == []:
                    print('Binance is being slow in returning the order, calling the API again...')

                    orders[coin] = client.get_all_orders(symbol=coin, limit=1)
                    time.sleep(1)

                else:
                    print('Order returned, saving order to file')

                    # Log trade
                    if LOG_TRADES:
                        write_log(f"Buy : {volume[coin]} {coin} - {last_price[coin]['price']}")


        else:
            print(f'Signal detected, but there is already an active trade on {coin}')

    return orders, last_price, volume


def sell_coins():
    '''sell coins that have reached the STOP LOSS or TAKE PROFIT threshold'''

    last_price = get_price()
    coins_sold = {}

    for coin in list(coins_bought):
        
        # define stop loss and take profit
        TP = float(coins_bought[coin]['bought_at']) + (float(coins_bought[coin]['bought_at']) * TAKE_PROFIT ) / 100
        SL = float(coins_bought[coin]['bought_at']) + (float(coins_bought[coin]['bought_at']) * STOP_LOSS ) / 100
        

        LastPrice = float(last_price[coin]['price'])
        BuyPrice = float(coins_bought[coin]['bought_at'])
        PriceChange = float((LastPrice - BuyPrice) / BuyPrice * 100)

        # check that the price is above the take profit and readjust SL and TP accordingly if trialing stop loss used
        if float(last_price[coin]['price']) > TP and USE_TRAILING_STOP_LOSS:
            print("TP reached, adjusting TP and SL accordingly to lock-in profit")
            
            # increasing TP by TRAILING_TAKE_PROFIT (essentially next time to readjust SL)
            coins_bought[coin]['take_profit'] += TRAILING_TAKE_PROFIT
            coins_bought[coin]['stop_loss'] = coins_bought[coin]['take_profit'] - TRAILING_STOP_LOSS

            continue

        # check that the price is below the stop loss or above take profit (if trailing stop loss not used) and sell if this is the case 
        if float(last_price[coin]['price']) < SL or (float(last_price[coin]['price']) > TP and not USE_TRAILING_STOP_LOSS):
            print(f"{txcolors.SELL}TP or SL reached, selling {coins_bought[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} : {PriceChange:.2f}%{txcolors.DEFAULT}")

            if TESTNET :
                # create test order before pushing an actual order
                test_order = client.create_test_order(symbol=coin, side='SELL', type='MARKET', quantity=coins_bought[coin]['volume'])

            # try to create a real order if the test orders did not raise an exception
            try:

                sell_coins_limit = client.create_order(
                    symbol = coin,
                    side = 'SELL',
                    type = 'MARKET',
                    quantity = coins_bought[coin]['volume']

                )

            # error handling here in case position cannot be placed
            except Exception as e:
                print(e)

            # run the else block if coin has been sold and create a dict for each coin sold
            else:
                coins_sold[coin] = coins_bought[coin]
                # Log trade

                if LOG_TRADES:
                    profit = (LastPrice - BuyPrice) * coins_sold[coin]['volume']
                    write_log(f"Sell: {coins_sold[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} Profit: {profit:.2f} {PriceChange:.2f}%")
            continue

        # no action
        print(f'TP or SL not yet reached, not selling {coin} for now {BuyPrice} - {LastPrice} : {PriceChange:.2f}% ')

    return coins_sold


def update_portfolio(orders, last_price, volume):
    '''add every coin bought to our portfolio for tracking/selling later'''
    if DEBUG: print(orders)
    for coin in orders:

        coins_bought[coin] = {
            'symbol': orders[coin][0]['symbol'],
            'orderid': orders[coin][0]['orderId'],
            'timestamp': orders[coin][0]['time'],
            'bought_at': last_price[coin]['price'],
            'volume': volume[coin],
            'stop_loss': -STOP_LOSS,
            'take_profit': TAKE_PROFIT,
            }

        # save the coins in a json file in the same directory
        with open(coins_bought_file_path, 'w') as file:
            json.dump(coins_bought, file, indent=4)

        print(f'Order with id {orders[coin][0]["orderId"]} placed and saved to file')


def remove_from_portfolio(coins_sold):
    '''Remove coins sold due to SL or TP from portfolio'''
    for coin in coins_sold:
        coins_bought.pop(coin)

    with open(coins_bought_file_path, 'w') as file:
        json.dump(coins_bought, file, indent=4)


def write_log(logline):
    timestamp = datetime.now().strftime("%d/%m %H:%M:%S")
    with open(LOG_FILE,'a+') as f:
        f.write(timestamp + ' ' + logline + '\n')



if __name__ == '__main__':
    print('Press Ctrl-Q to stop the script')

    if not TESTNET:
        print('WARNING: You are using the Mainnet and live funds. Waiting 30 seconds as a security measure')
        time.sleep(30)

    for i in count():
        orders, last_price, volume = buy()
        update_portfolio(orders, last_price, volume)
        coins_sold = sell_coins()
        remove_from_portfolio(coins_sold)
