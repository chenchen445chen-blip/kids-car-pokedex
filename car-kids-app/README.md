# 儿童汽车认知与拍照识别 App 前端 (car-kids-app)

基于 **uni-app x (Vue 3 + UTS / UVUE)** 构建，1:1 还原设计稿 `Colorful Kids’ Car Learning App Mockup.png` 中的全部 10 个核心页面，并与 `car-kids-server` FastAPI 后端真实字段直连。

## 页面结构与设计稿对应关系

| 页面路径 | 对应 UI 设计稿位置 | 核心功能 |
|---|---|---|
| `pages/index/index.uvue` | 上排第 1 张（首页） | 蓝天草地卡通背景、「拍照识车」与「汽车图鉴」双大入口、最近浏览、家长设置 |
| `pages/recognition/camera.uvue` | 上排第 2 张（拍照识车） | 四角白色取景引导框、拍摄提示、底部蓝色「拍照」与绿色「相册」圆形大按钮 |
| `pages/recognition/result.uvue` | 上排第 3 张（识别结果） | 识别汽车实拍图、品牌车标+名称（如宝马 3系）、分类标签、灯泡儿童知识卡片、「查看更多」 |
| `pages/catalog/index.uvue` | 上排第 4 张 & 下排第 1 张 | 汽车图鉴：「按类型」（7大一级分类）与「按品牌」（九宫格品牌列表+分组筛选）双 Tab 切换 |
| `pages/catalog/category-vehicles.uvue` | 上排第 5 张（工程车） | 分类下已审核车型双列网格（挖掘机、装载机、推土机、起重机、压路机、混凝土搅拌车等） |
| `pages/brand/detail.uvue` | 下排第 2 张（奔驰） | 品牌大车标、品牌名、标语、产品线分组（如王朝/海洋）与车系列表（C级/E级/S级） |
| `pages/series/detail.uvue` | 下排第 3 张（E级） | 车系大图、多角度缩略图预览、儿童版车系简介、下属具体车型列表 |
| `pages/vehicle/detail.uvue` | 下排第 4 张（奔驰 E级） | 年款标签（`2024款`）、车型大标题、轿车/品牌/家用车属性、实拍/模型标识、灯泡知识卡 |
| `pages/recognition/pending.uvue` | 下排第 5 张（审核中） | 卡通工程车插画、「该车型正在审核中 / 我们正在完善相关信息，请稍后再来查看」、「返回图鉴」 |
| `pages/parent/settings.uvue` | 首页底部入口 | 儿童隐私保护说明、Mac 后端服务地址配置与连通性测试、清除本机浏览记录 |

## 运行说明

1. 先启动后端服务 `car-kids-server`（默认监听 `http://127.0.0.1:8088`）。
2. 如需运行到微信小程序，请在本地 `manifest.json` 的 `mp-weixin.appid` 中填入你自己的微信小程序 AppID（切勿将含个人隐私凭证的编译产物提交到公开仓库）。
3. 使用 HBuilderX 打开 `car-kids-app` 目录，选择运行到微信开发者工具、浏览器或 Android/iOS 模拟器。

## 免责与非商业科研声明

- 本项目仅用于计算机视觉、儿童认知交互与软件工程相关的**学术科研及教学演示**，严禁用于任何商业盈利目的。
- 项目中所涉及的汽车品牌名称、车型名称及相关标识仅用于客观知识科普展示，其商标权与知识产权均归各对应汽车厂商所有。


