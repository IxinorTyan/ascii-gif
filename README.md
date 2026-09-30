# Suzu ASCII Studio (纯静态 Web 版)

> 把动态画面，变成流动的字符。  
> 100% 纯前端静态网页应用，零服务器依赖，视频/GIF 均在浏览器本地秒级解码处理。

---

## ✦ 特性亮点

1. **零服务器依赖（纯静态）**：
   - 彻底脱离 Python 后端，核心编解码与字符计算均由浏览器在本地离线完成。
   - 无需担心服务器带宽与高额算力消耗，用户选择多大的视频都不会上传到网络，安全且私密。
2. **现代浏览器媒体解码**：
   - **GIF**：采用纯 JavaScript 内存级 GIF89a 状态机解码，精确还原各帧时间戳与 Disposal 覆盖方式。
   - **视频**：利用浏览器原生 HTML5 Video + Offscreen Canvas，支持 MP4 (H.264)、WebM、MOV 等格式。
3. **多种格式一键导出**：
   - **流畅背景 HTML**：Canvas 高性能字符绘制，适合整页背景，自动循环、无按钮铺满。
   - **可复制字符动画 HTML**：DOM 文本复用优化，支持重播、进度、倍速与字符框选复制。
   - **ASCII GIF 图片**：内置轻量量化与 LZW 压缩编码，直接生成标准的 `.gif` 动图。

---

## 🚀 部署到 Cloudflare Pages

本项目是纯静态网站，可以零配置部署到 **Cloudflare Pages**：

1. 将本仓库推送到 GitHub / GitLab。
2. 进入 Cloudflare 控制台，点击 **Workers & Pages** -> **Create application** -> **Pages** -> **Connect to Git**。
3. 选择你的仓库，进入 **Set up builds and deployments**：
   - **Framework preset (框架预设)**: `None`
   - **Build command (构建指令)**: **留空（不填）**
   - **Build output directory (构建输出目录)**: **留空 或填 `/`**
4. 点击 **Save and Deploy** 即可，0 秒构建，立即全球生效！

---

## 💻 本地运行

- **Windows 用户**：直接双击根目录下的 `启动.bat`，即可启动本地轻量静态服务并自动在浏览器中打开。
- **命令行**：
  ```bash
  # Python 方式
  python -m http.server 8765

  # 或 Node.js 方式
  npx serve .
  ```
- **自动化测试**：
  ```bash
  node --test tests/*.test.mjs
  ```

---

## 📄 开源声明与致谢

- 字符处理算法与预设改编自 SuzuVisualLab (MIT License)，详见 `LICENSE-SuzuVisualLab`。
- GIF 编解码核心基于 `omggif` 与 `gifenc`。
