# tradingview-alert-webhook for binance-api
TradingView Strategy Alert Webhook that buys and sells crypto with the Binance API
This script work on both one-way mode and Hegde mode.
# Script is compatible with the follwing strategy message
##### passphrase should be = SECRET_KEY
##### Open Position can use "$20" or "@0.02" for determined size In my case I can use "@xxx" as VXD auto calculate size 
##### Close Position or TP can use "%xx" as this script will pull your position amount and calculated it,
##### for Example "amount": "%50" for TP 1 and "%100" for TP2

# Sample payload 
```
{"side":"OpenShort","amount":"@0.006","symbol":"BTCUSDTPERP","passphrase":"1234","leverage":"125"}
```
# There is 7 Vars Setting for HEROKU
1. API_KEY    	= your api key
2. API_SECRET	= your api secret key
3. LINE_TOKEN   = your Line-notify token can be genarated @https://notify-bot.line.me/en/
4. BOT_NAME		= any name
5. FREEBALANCE	= Min balance for trade(Bot will Halted if FREEBALANCE < Equity)
6. SECRET_KEY	= your passphrase form tradingview signal
7. ORDER_ENABLE = "TRUE" = Enable Bots "FALSE" = Disable Bots

```
 passphrase = input.string(defval='xxxx', title ='Bot Pass',group='═ Bot Setting ═')
 leveragex  = input.int(125,title='leverage',group='═ Bot Setting ═',tooltip='"NOTHING" to do with Position size',minval=1)
 Alert_OpenLong       = '{"side": "OpenLong", "amount": "@{{strategy.order.contracts}}", "symbol": "{{ticker}}", "passphrase": "'+passphrase+'","leverage":"'+str.tostring(leveragex)+'"}'
 Alert_OpenShort      = '{"side": "OpenShort", "amount": "@{{strategy.order.contracts}}", "symbol": "{{ticker}}", "passphrase": "'+passphrase+'","leverage":"'+str.tostring(leveragex)+'"}'
 Alert_LongTP         = '{"side": "CloseLong", "amount": "@{{strategy.order.contracts}}", "symbol": "{{ticker}}", "passphrase": "'+passphrase+'","leverage":"'+str.tostring(leveragex)+'"}'
 Alert_ShortTP        = '{"side": "CloseShort", "amount": "@{{strategy.order.contracts}}", "symbol": "{{ticker}}", "passphrase": "'+passphrase+'","leverage":"'+str.tostring(leveragex)+'"}'
 message_closelong       = '{"side": "CloseLong", "amount": "%100", "symbol": "{{ticker}}", "passphrase": "'+passphrase+'","leverage":"'+str.tostring(leveragex)+'"}'
 message_closeshort      = '{"side": "CloseShort", "amount": "%100", "symbol": "{{ticker}}", "passphrase": "'+passphrase+'","leverage":"'+str.tostring(leveragex)+'"}'
```
## Vaz
