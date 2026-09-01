# binance-mcp-server tool inventory

Snapshot taken 2026-09-01 during read-only smoke test. 62 tools visible to this
session. Grouped by whether the tool can change account state.

## WRITE (can change account state) — 3 visible

spot_newOrder
spot_deleteOrder
spot_deleteOpenOrders

## META / PROXY — 2 visible

tool_execute   — executes ANY server tool by name, including hidden ones not in
                 the visible 62. Args: {toolName, arguments}. This is a write
                 path: it can invoke spot.newOrder and every hidden trade tool
                 listed below. Treat as write-capable.
tool_search    — read-only. Lists the server's full tool registry by category
                 (account, trade, borrow-repay, transfer, market-data, ...),
                 paginated. Reveals hidden tools callable via tool_execute.

## READ (query only) — 57 visible

analysis_getTokenAiReport
convert_getConvertTradeHistory
convert_listAllConvertPairs
convert_orderStatus
convert_queryLimitOpenOrders
convert_queryOrderQuantityPrecisionPerAsset
futures_coin_accountInformation
futures_coin_continuousContractKlineCandlestickData
futures_coin_currentAllOpenOrders
futures_coin_exchangeInformation
futures_coin_futuresAccountBalance
futures_coin_indexPriceKlineCandlestickData
futures_coin_klineCandlestickData
futures_coin_markPriceKlineCandlestickData
futures_coin_positionInformation
futures_coin_premiumIndexKlineData
futures_coin_queryOrder
futures_coin_symbolPriceTicker
futures_usds_accountInformationV3
futures_usds_continuousContractKlineCandlestickData
futures_usds_currentAllOpenOrders
futures_usds_exchangeInformation
futures_usds_futuresAccountBalanceV3
futures_usds_indexPriceKlineCandlestickData
futures_usds_klineCandlestickData
futures_usds_markPriceKlineCandlestickData
futures_usds_positionInformationV2
futures_usds_premiumIndexKlineData
futures_usds_queryOrder
futures_usds_symbolPriceTicker
margin_crossMarginCollateralRatio
margin_getAllIsolatedMarginSymbol
margin_getAllMarginAssets
margin_queryCrossMarginAccountDetails
margin_queryMarginAccountsAllOrders
margin_queryMarginAccountsOpenOrders
margin_queryMarginAccountsOrder
margin_queryMarginAccountsTradeList
margin_queryMaxBorrow
spot_depth
spot_exchangeInfo
spot_getAccount
spot_getOpenOrders
spot_getOrder
spot_klines
spot_myTrades
spot_newOrder (listed above as WRITE; not repeated in count)
spot_ticker24hr
spot_tickerPrice
spot_uiKlines
wallet_accountStatus
wallet_allCoinsInformation
wallet_dailyAccountSnapshot
wallet_depositAddress
wallet_depositHistory
wallet_getApiKeyPermission
wallet_queryUserUniversalTransferHistory
wallet_queryUserWalletBalance

Note: futures_* account/position/order tools are exposed but return
{"code":-2015,"msg":"Invalid API-key, IP, or permissions for action"} because
the key has enableFutures=false. futures_* kline/ticker/exchangeInfo tools are
public market-data endpoints and work without account permission.

## HIDDEN write tools reachable via tool_execute (from tool_search category=trade)

All spot-only. No margin order tools, no futures order tools, no borrow/repay,
no transfer execution tools exist anywhere in the registry.

spot.newOrder
spot.deleteOrder
spot.deleteOpenOrders
spot.deleteOrderList
spot.orderAmendKeepPriority
spot.orderCancelReplace
spot.orderOco (deprecated)
spot.orderListOco
spot.orderListOpo
spot.orderListOpoco
spot.orderListOto
spot.orderListOtoco
spot.sorOrder
spot.orderTest (validation only, never reaches matching engine)
spot.sorOrderTest (validation only)

## Verified absent

- Margin BORROW/REPAY execution: none. borrow-repay category contains only
  queries (margin.queryMaxBorrow, margin.queryBorrowRepayRecordsInMarginAccount,
  interest-rate/history queries).
- Transfer execution: none. transfer category contains only
  margin.getCrossMarginTransferHistory and margin.queryMaxTransferOutAmount.
- Master-account read: no sub-account or master-account tool exists in the
  visible list or the searched registry categories.
