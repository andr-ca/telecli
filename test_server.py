#!/usr/bin/env python3
"""
Simple test server to debug Cloudflare tunnel issues
"""
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app = FastAPI(title="TeleCLI Test Server")

# Add middleware to handle reverse proxy headers
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"Request: {request.method} {request.url}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Path: {request.url.path}")
    print(f"Query: {request.url.query}")
    print("-" * 50)
    
    try:
        response = await call_next(request)
        print(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        print(f"Error processing request: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/")
async def root():
    return {"message": "TeleCLI Test Server", "status": "ok"}

@app.get("/debug")
async def debug_info(request: Request):
    return {
        "url": str(request.url),
        "method": request.method,
        "headers": dict(request.headers),
        "path": request.url.path,
        "query": request.url.query,
        "host": request.headers.get("host"),
        "x_forwarded_for": request.headers.get("x-forwarded-for"),
        "x_forwarded_proto": request.headers.get("x-forwarded-proto"),
        "x_forwarded_host": request.headers.get("x-forwarded-host"),
        "cf_ray": request.headers.get("cf-ray"),
        "cf_connecting_ip": request.headers.get("cf-connecting-ip"),
    }

@app.get("/test")
async def test():
    return {"test": "success", "message": "Server is working correctly"}

if __name__ == "__main__":
    print("Starting test server...")
    print("Access via:")
    print("  Local: http://localhost:8801/")
    print("  Tunnel: https://code.andr.ca/telecli/")
    print("  Debug: /debug endpoint for request info")
    print("  Test: /test endpoint for simple test")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8801,
        access_log=True,
        server_header=False,
        date_header=False,
        forwarded_allow_ips="*",
        proxy_headers=True,
    )