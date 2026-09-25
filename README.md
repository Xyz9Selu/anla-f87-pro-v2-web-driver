# AULA 键盘驱动 — 本地离线版

源站: https://hev.aulacn.com/#/ (Vue SPA, 有 WAF, 直接 curl 会 403)
本目录是抓取后的可运行本地包, 已验证 `http://127.0.0.1:8080/#/` 能打开。

## 1. 启动 (必须用 server, 不能双击 index.html)

```bash
./start.sh                 # 在线模式: 缺啥自动从 CDN 拉取并缓存
./start.sh --offline       # 真离线测试: 只读本地缓存, 缺文件直接 404
./start.sh --port 8080     # 默认 8080
```

浏览器打开: http://127.0.0.1:8080/#/

为什么不能 `file://` 双击打开:
JS 里打过补丁, 用的是绝对路径 `/cdn_static/...` `/cfg/...` `/api/...`,
只有经过 `server.py` 才能解析。`file://` 下这些路径全部 404。

## 2. 目录结构

```
index.html              # 首页 (已去统计 bt-stats.js, favicon 本地化, 标题 AULA offline)
96497d6bd8989bff.wasm   # 根目录 wasm (原站 /96497....wasm, 需 WAF cookie 才抓得到)
static/js/*.js          # 5 个 bundle (app / vendors / keyboard / elementUI / pintura)
static/js/*.js.orig     # 补丁前备份 (保留, 别删)
static/css/*.css
static/img/*            # 36 个语言旗 svg + 灯效图标 + key_switch
static/fonts/*          # element-icons + iconfont
cdn_static/keyboards/*  # ~150 张键盘底图 (原 https://static.driveall.cn/static/keyboards/)
cdn_static/mouses/hfd.png
cfg_cache/              # 原 https://config.driveall.cn/* 的本地缓存
  axial.json, gif/defaultGif.json, logo/..., protocol/...
server.py               # 本地服务器 + 缓存代理 (唯一需要运行的东西)
start.sh                # 启动脚本: python3 server.py "$@"
```

## 3. server.py 路由 (JS 已按此打补丁)

| 前端请求 | 本地命中 | 未命中 (在线模式) |
|---|---|---|
| `/cdn_static/*` | `cdn_static/*` | 抓 `https://static.driveall.cn/static/*` 并缓存 |
| `/cfg/*` | `cfg_cache/*` | 抓 `https://config.driveall.cn/*` 并缓存 |
| `/api/*` | — | 透传 `https://cp.driveall.cn/api/*` (云登录/分享, 不缓存) |
| `http://127.0.0.1:9191/...` | — | 不经过本服务, 直连键盘 USB 守护进程 |

补丁内容 (`static/js/*.js` vs `*.orig`):
- `https://static.driveall.cn/static` → `/cdn_static` (2+4 处)
- `https://config.driveall.cn` → `/cfg` (13+16 处)
- `https://cp.driveall.cn` 保留: localhost 下 hostname 不含 `.cn`,
  代码自动走相对路径 `/api/*`, 正好被 server.py 接住。

## 4. 离线程度 (实话)

- ✅ 已离线: 首页框架、全部 JS/CSS/字体/图标、150+ 键盘底图、
  axial.json、默认 GIF、logo、协议页、wasm。
- ⚠️ 半离线: `config.json/json/<type>/<name>.json`、
  `gif-lighting/<id>.json`、`gif/<screen>/defaultGif.json` 按键盘型号动态加载,
  无法事先枚举。首次必须在线连一次键盘、把页面点一遍, server 会自动缓存到
  `cfg_cache/`, 之后 `--offline` 才能完整显示该型号。
- ❌ 无法离线: 云登录/分享/上传 (`/api/*`, 需 cp.driveall.cn)、
  键盘 USB 控制本身 (`127.0.0.1:9191` 守护进程必须另装运行, 网页只是它的 UI)、
  `Music.exe` 大文件未抓 (用时在线下, 或手动放 `cfg_cache/music/v2/Music.exe`)。
- 已知 404 (可忽略): JS 里引用的 10 张旧键盘图
  (Epomaker_TH108_ISO/TH87_JIS/G84_Pro/TH108_JP、GOYO_108、
  Mechlands_Vibe108、GS3087T-PRO/GS101T、SG9079) 和 `gif/defaultGif2.json`,
  远端已删, 代码有 fallback。

## 5. 重新抓取 / 更新

源站有 WAF (首次 403 + set-cookie, 带 cookie 重试才 200, 见抓取记录)。
CDN (`static/config/cp.driveall.cn`) 无 WAF, 可直连。
前端 hash 变了 (如 `app.xxxxx.js`) 就按 `index.html` 重新拉一遍即可,
补丁脚本见本次会话记录 (`mirror.py` 逻辑), 恕不另存。

## 6. F87 Pro V2 已预热 (2026-09-25)

`cfg_cache/` 内已含 F87 Pro V2 (Z/D/C, 有线/Dongle, productId
10000/10001/10002/65276/65278) 的全部动态配置, `--offline` 下 7/7 通过:

- 底图 `cdn_static/keyboards/2902.png`
- `tftConfig.localforageKey=r7c7` 的 15 个内置灯效
  `json/r7c7/{aula,chart,happy,iLoveYou,meteorShower,bouncingBall,`
  `rollingColorBar,rollingRedHeart,rollingBall,exciteMood,`
  `failingAtBothEnds,floatingfern,sokoban,downFloor,spinballs}.json`
- `gif-lighting/{heartRateCurve_87,heart_87}.json`
  (effectConfig.gifEffectIds, F87 无磁轴/无屏幕专属 gif, 通用
  `gif/defaultGif.json` + `axial.json` 已在包内)

## 7. 下一步 (二选一, 告诉我)

1. 报你的键盘型号 (如 AK820), 我在线预热一遍, 把它的 json/gif-lighting
   一起打进 `cfg_cache/` 交给你真正离线的包。
2. 要我再写个 `prefetch.py <型号>` 脚本, 你自己插上键盘后一键暖缓存。
