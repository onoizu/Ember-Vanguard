# Ember Vanguard Web

根据仓库 GDD 重构的本地网页版本。游戏保留二维坐标地图、三种角色背景、隐藏 D20、诅咒检定、20 房间异变、连续终局和五种结局。

## 本地运行

    npm install
    npm run dev

浏览器打开终端输出的本地地址。

## 操作

- 遭遇：数字键 1 / 2 / 3 或点击行动按钮
- 移动：W / A / S / D、方向按钮或地图上的相邻房间
- 进度：自动保存到浏览器 localStorage

## 验证

    npm run lint
    npm test

## 结构

- app/：网页入口、全局视觉与社交分享信息
- components/：角色选择、状态 HUD、地图、叙事与结局界面
- hooks/：浏览器存档及键盘控制
- lib/game/：游戏数据结构、离线内容和纯状态机
- worker/：Sites / Cloudflare Worker 运行入口

当前版本使用内置叙事 fallback，能够在本地独立完成整局游戏。后续接入远程 LLM 时，只需为 lib/game 增加叙事 Provider；地图与规则状态机不需要重写。
