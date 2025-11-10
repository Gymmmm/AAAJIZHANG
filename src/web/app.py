"""
FastAPI Web应用主程序
"""
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from .api import router as api_router
from .auth import get_current_user
from ..models import User, init_db


# 创建FastAPI应用
app = FastAPI(title="记账机器人SaaS平台", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
static_dir = Path(__file__).parent.parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 配置模板
templates_dir = Path(__file__).parent.parent.parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# 注册API路由
app.include_router(api_router, prefix="/api")


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup_event():
    """启动时初始化数据库"""
    await init_db()


# ==================== 页面路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """用户后台"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """管理员后台"""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/bills/{bot_id}", response_class=HTMLResponse)
async def bills_page(request: Request, bot_id: int):
    """账单页面"""
    return templates.TemplateResponse("bills.html", {
        "request": request,
        "bot_id": bot_id
    })


# ==================== 健康检查 ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
