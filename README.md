# 儿童汽车认知乐园 (Kids Car Pokedex)

面向 3—5 岁儿童及家长的汽车认知与拍照识别系统，包含前端小程序/App 与后端图鉴服务两个子项目：

## 项目结构

- **[`car-kids-app/`](./car-kids-app)**：基于 `uni-app x (Vue 3 + UTS / UVUE)` 构建的跨端应用（支持微信小程序、App、H5），包含首页、拍照识车、双维汽车图鉴（按类型/按品牌）、随机看车卡片流及家长设置。
- **[`car-kids-server/`](./car-kids-server)**：基于 `Python + FastAPI + SQLite` 构建的后端服务，提供四级汽车品牌/车系图鉴检索、三级拍照识车匹配、待审核草稿箱与受控图片服务。

## 快速开始

### 1. 启动后端服务 (`car-kids-server`)

```bash
cd car-kids-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# 启动服务（首次运行将自动建表并生成内置合规纯色演示图库）
uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload
```

### 2. 启动前端应用 (`car-kids-app`)

1. 使用 HBuilderX 打开 `car-kids-app` 目录。
2. 如需运行至微信小程序，请在本地 `car-kids-app/manifest.json` 的 `mp-weixin.appid` 中填写你自己的小程序 AppID。
3. 点击「运行」→「运行到小程序模拟器」或「运行到浏览器」。

## 免责与非商业科研声明

- 本仓库代码仅用于计算机视觉、儿童认知交互与软件工程相关的**学术科研及教学演示**，严禁用于任何商业盈利目的。
- 仓库不包含任何受第三方版权保护的实拍车辆图片或商业商标原图；首次启动后端时由 `app/db/seed.py` 自动生成纯色圆角示意卡片。
- 项目中提及的汽车品牌名称与车型名称仅作客观知识科普演示，相关商标权归各汽车厂商所有。
