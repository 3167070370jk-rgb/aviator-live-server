import asyncio
import json
import websockets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import os

app = FastAPI()

app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

results = []
live_mult = 0.0
current_round = None
ws_status = "disconnected"

WS_TOKEN = os.environ.get("WS_TOKEN","")
WS_BASE = os.environ.get("WS_BASE","wss://crashbot.grupoaviatorcolombia.com/api/v1/ws/live?ticket=")
WS_COOKIE = os.environ.get("WS_COOKIE","")

async def connect_casino():
 global live_mult,current_round,ws_status
 if not WS_TOKEN:
  ws_status="no_token"
  return
 url=WS_BASE+WS_TOKEN
 headers={"Origin":"https://crashbot.grupoaviatorcolombia.com","User-Agent":"Mozilla/5.0"}
 if WS_COOKIE:
  headers["Cookie"]=WS_COOKIE
 while True:
  try:
   async with websockets.connect(url,ping_interval=20,extra_headers=headers) as ws:
    ws_status="connected"
    print("[WS] Conectado")
    async for message in ws:
     try:
      msg=json.loads(message)
      await handle_message(msg)
     except:
      pass
  except Exception as e:
   ws_status="reconnecting"
   print(f"[WS] Error:{e}")
   await asyncio.sleep(5)

async def handle_message(msg):
 global live_mult,current_round
 if msg.get("type")=="live_mult" and "x" in msg:
  live_mult=float(msg["x"])
  current_round=msg.get("round_id")
 if msg.get("type")=="round" and "multiplier" in msg:
  v=float(msg["multiplier"])
  ts=msg.get("started_at",datetime.utcnow().isoformat()+"Z")
  results.insert(0,{"odd":v,"date":ts,"round_id":msg.get("game_round_id")})
  if len(results)>500:
   results.pop()
  print(f"[Ronda] {v}x")
 if msg.get("type")=="live_state" and msg.get("state")==1:
  live_mult=1.0
  current_round=msg.get("round_id")

@app.get("/")
def root():
 return {"status":"Aviator Live Server OK","results":len(results)}

@app.get("/live")
def get_live():
 return {"multiplier":live_mult,"round_id":current_round,"ws_status":ws_status}

@app.get("/history")
def get_history(limit:int=200):
 return results[:limit]

@app.get("/stats")
def get_stats():
 if not results:
  return {"total":0}
 vals=[r["odd"] for r in results]
 return {"total":len(vals),"average":round(sum(vals)/len(vals),2),"max":max(vals),"win_rate_2x":round(len([v for v in vals if v>=2])/len(vals)*100,1),"last":vals[0],"ws_status":ws_status}

@app.on_event("startup")
async def startup():
 asyncio.create_task(connect_casino())

if __name__=="__main__":
 port=int(os.environ.get("PORT",8000))
 uvicorn.run("main:app",host="0.0.0.0",port=port)
