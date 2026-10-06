from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fyers_apiv3 import fyersModel
import datetime
from typing import Optional

FYERS_ACCESS_TOKEN = None

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

client_id = '8PNBJSARNA-100'
secret_key = 'WMLJO1VM7Z'
redirect_uri = 'http://127.0.0.1:8000/login'

import os

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/fyers_auth_url")
async def get_fyers_auth_url():
    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type='code',
        grant_type='authorization_code'
    )
    auth_link = session.generate_authcode()
    return {"url": auth_link}

@app.get("/login")
async def fyers_login(auth_code: Optional[str] = None):
    global FYERS_ACCESS_TOKEN
    
    # Use your actual credentials here
    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code"
    )

    # Step 1: Initial Click -> Redirect to Fyers
    if not auth_code:
        auth_url = session.generate_authcode()
        return RedirectResponse(url=auth_url)

    # Step 2: Callback from Fyers -> Generate and Save Token
    session.set_token(auth_code)
    response = session.generate_token()

    if response.get("s") == "ok":
        FYERS_ACCESS_TOKEN = response.get("access_token")
        print("Successfully generated Access Token!")
        return RedirectResponse(url="/")
    else:
        print("Fyers Token Error:", response)
        return {"error": "Failed to get access token", "details": response}

@app.get("/api/check_auth")
def check_auth():
    global FYERS_ACCESS_TOKEN
    return {"is_logged_in": FYERS_ACCESS_TOKEN is not None}

@app.post("/api/logout")
async def logout():
    global FYERS_ACCESS_TOKEN
    FYERS_ACCESS_TOKEN = None
    return {"status": "ok"}

@app.get("/api/chart_data")
async def get_chart_data(symbol: str, timeframe: str = "1d"):
    global FYERS_ACCESS_TOKEN
    if not FYERS_ACCESS_TOKEN:
        return {"error": "Not authenticated"}
        
    resolution_map = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "1d": "1D",
        "1wk": "1W",
        "1mo": "1M"
    }
    
    res = resolution_map.get(timeframe)
    if not res:
        raise HTTPException(status_code=400, detail="Invalid timeframe")
        
    end_date_global = datetime.date.today()
    fyers = fyersModel.FyersModel(client_id=client_id, is_async=False, token=FYERS_ACCESS_TOKEN, log_path="")
    
    all_candles = []
    
    if timeframe in ["1m", "5m", "15m"]:
        start_date_global = end_date_global - datetime.timedelta(days=365)
        current_start = start_date_global
        
        while current_start <= end_date_global:
            current_end = current_start + datetime.timedelta(days=90)
            if current_end > end_date_global:
                current_end = end_date_global
                
            data = {
                "symbol": symbol,
                "resolution": res,
                "date_format": "1",
                "range_from": current_start.strftime("%Y-%m-%d"),
                "range_to": current_end.strftime("%Y-%m-%d"),
                "cont_flag": "1"
            }
            
            response = fyers.history(data=data)
            if response.get("s") == "ok":
                all_candles.extend(response.get("candles", []))
            
            # Prevent infinite loop if already at end_date_global
            if current_end == end_date_global:
                break
                
            current_start = current_end + datetime.timedelta(days=1)
    else:
        start_date = end_date_global - datetime.timedelta(days=365)
        data = {
            "symbol": symbol,
            "resolution": res,
            "date_format": "1",
            "range_from": start_date.strftime("%Y-%m-%d"),
            "range_to": end_date_global.strftime("%Y-%m-%d"),
            "cont_flag": "1"
        }
        
        response = fyers.history(data=data)
        if response.get("s") != "ok":
            raise HTTPException(status_code=400, detail=f"Fyers API Error: {response.get('message', 'Unknown error')}")
        all_candles.extend(response.get("candles", []))
        
    unique_candles = {}
    for candle in all_candles:
        unique_candles[candle[0]] = candle
        
    sorted_candles = sorted(unique_candles.values(), key=lambda x: x[0])
    
    return {"candles": sorted_candles}
